"""归档候选、去重与写入前复核；归档通过 session.time_archived 短事务写入并核验。

与 Codex 原版的差异：ZCode 会话库可直读，保护名单实时计算（当前会话、锁定、
子代理、用户指定），不再依赖宿主列表快照与定时任务清单。
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import sys
import time

from zcode_adapter import BackendError, ModelSkipped, ZCodeBackend, generate_json
from kk_zcode_title import (ROOT, atomic_json, data_dir, load_config, read_json,
                            item_text, project_hint, state_path, thread_lock,
                            valid_id, worker_slot)

DAY = 86400
CONTEXT_VERSION = 3
MAX_CONTEXT_CHARS = 12000
POLICY = {"enabled": False, "completed_days": 14, "inactive_days": 30, "protected_ids": []}
SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "classification": {"type": "string", "enum": ["completed", "no_pending", "open", "uncertain"]},
    "reason": {"type": "string"}}, "required": ["classification", "reason"]}


def policy(root):
    value = POLICY | read_json(root / "archive/config.json")
    if type(value["enabled"]) is not bool:
        raise ValueError("归档开关必须是布尔值")
    if not all(type(value[k]) is int for k in ("completed_days", "inactive_days")) or not (
        1 <= value["completed_days"] <= value["inactive_days"] <= 365
    ):
        raise ValueError("归档天数必须满足 1 ≤ 已完成 ≤ 无待办 ≤ 365")
    value["protected_ids"] = [valid_id(i) for i in value["protected_ids"]]
    return value


def record_path(root, tid):
    return root / "archive/threads" / (valid_id(tid) + ".json")


def live_guards(root, current_id=None):
    """实时保护名单：当前会话、用户指定保护、已锁定标题的会话。"""
    protected = set()
    if current_id:
        protected.add(valid_id(current_id))
    cfg = policy(root)
    protected.update(cfg["protected_ids"])
    for path in (root / "threads").glob("*.json"):
        try:
            if read_json(path).get("locked"):
                protected.add(path.stem)
        except (ValueError, OSError):
            continue
    return protected


def archive_context(thread):
    """归档专用完整文本；超过预算就保留，不能遗漏中间或末尾的待办。"""
    effective, original = [], ""
    turns = thread.get("turns", [])
    for index, turn in enumerate(turns):
        messages = []
        for item in turn.get("items", []):
            kind = item.get("type")
            if kind not in ("userMessage", "agentMessage"):
                continue
            text = item_text(item)
            if text:
                role = "user" if kind == "userMessage" else "assistant"
                messages.append({"role": role, "text": text})
                if role == "user" and not original:
                    original = text
        if messages and index >= len(turns) - 5:
            effective.append({"id": turn["id"], "messages": messages})
    if not original or not effective:
        return None
    context = {"current_title": thread.get("name") or "", "project_hint": project_hint(thread),
               "original_goal": original, "recent_turns": effective[-5:]}
    if len(json.dumps(context, ensure_ascii=False)) > MAX_CONTEXT_CHARS:
        return None
    return context


def activity(thread):
    """使用最后完成轮次的时间和内容版本；未完成轮次的话题不参与归档。"""
    turns = thread.get("turns", [])
    if not turns:
        return None
    latest = turns[-1]
    final = next((i for i in latest["items"] if i["type"] == "agentMessage"), None)
    if final is None:
        return None  # 最后一轮未完成或被中断
    stamp = final.get("completed_at")
    if type(stamp) not in (int, float) or stamp <= 0:
        return None
    context = archive_context(thread)
    if context is None:
        return None
    # 包括未截断的最近轮次，避免内容末尾变化未进入摘要时错误复用。
    encoded = json.dumps({"turns": turns[-5:]}, sort_keys=True, ensure_ascii=False)
    return stamp / 1000, hashlib.sha256(encoded.encode()).hexdigest(), context


def protected(thread, tid, cfg, guard_ids, root):
    if tid in guard_ids or tid in cfg["protected_ids"]:
        return True
    if thread.get("parent_id") or "subagent" in tid:
        return True  # 子代理会话跟随主会话生命周期
    return bool(read_json(state_path(root, tid)).get("locked"))


def eligible(classification, age, cfg):
    return ((classification == "completed" and age >= cfg["completed_days"] * DAY)
            or (classification == "no_pending" and age >= cfg["inactive_days"] * DAY))


def classify(root, config, context, *, before_model=None):
    deadline = time.monotonic() + config["model_timeout_seconds"]
    with worker_slot(root, config["max_parallel_workers"], config["model_timeout_seconds"]) as acquired:
        remaining = deadline - time.monotonic()
        if not acquired or remaining <= 0:
            raise BackendError("模型并发已满，保留话题")
        return generate_json({**config, "model_timeout_seconds": remaining}, context,
                             ROOT / "prompts/archiving.md", SCHEMA,
                             before_model=before_model, state_dir=root)


def scan(backend, root, classifier=None, max_evaluations=10, *, scheduled=False, current_id=None):
    """预览也持久化评估缓存；同一内容版本只尝试一次模型，失败不自动重试。"""
    now = time.time()
    cfg = policy(root)
    if scheduled and not cfg["enabled"]:
        return {"status": "disabled", "enabled": False, "counts": {}, "candidates": []}
    guard_ids = live_guards(root, current_id)

    def ensure_scan_active():
        fresh = policy(root)
        if ((scheduled or cfg["enabled"]) and not fresh["enabled"]
                or fresh.get("pause_revision") != cfg.get("pause_revision")):
            raise ModelSkipped("disabled")

    stopped = False
    counts, candidates = Counter(), []
    with thread_lock(root / "archive", "scan") as acquired:
        if not acquired:
            return {"status": "busy"}
        for meta in backend.list_sessions(archived=False):
            try:
                ensure_scan_active()
            except ModelSkipped:
                stopped = True
                break
            tid = valid_id(meta["id"])
            counts["listed"] += 1
            state = read_json(record_path(root, tid))
            # 归档终态优先于任何内容读取或模型。手工恢复后仍保护，需显式 release。
            if state.get("archived_at") or state.get("protected"):
                counts["terminal_or_protected"] += 1
                continue
            if protected(meta, tid, cfg, guard_ids, root):
                counts["protected"] += 1
                continue
            try:
                thread = backend.read(tid)
                if protected(thread, tid, cfg, guard_ids, root):
                    counts["protected"] += 1
                    continue
                info = activity(thread)
                if info is None:
                    counts["unknown_activity"] += 1
                    continue
                stamp, fingerprint, context = info
                age = now - stamp
                if age < cfg["completed_days"] * DAY:
                    counts["recent"] += 1
                    continue
                if state.get("fingerprint") == fingerprint:
                    counts["cached"] += 1
                    if state.get("context_version") != CONTEXT_VERSION:
                        # 不复用旧版本摘要的正向结论，也不自动清缓存再次收费。
                        counts["legacy_kept"] += 1
                        continue
                else:
                    if classifier is None or counts["model_attempts"] >= max_evaluations:
                        counts["awaiting_evaluation"] += 1
                        continue

                    def before_model():
                        ensure_scan_active()
                        if backend.is_archived(tid):
                            raise ModelSkipped("archived")
                        fresh = backend.read(tid)
                        fresh_info = activity(fresh)
                        if (protected(fresh, tid, policy(root), live_guards(root, current_id), root)
                                or not fresh_info or fresh_info[1] != fingerprint):
                            raise ModelSkipped("stale")
                    before_model()
                    # 先落盘再调用，崩溃/异常不会导致下一次无界重试。
                    state = {"fingerprint": fingerprint, "context_version": CONTEXT_VERSION,
                             "classification": "uncertain",
                             "reason": "评估未完成，自动保留；需要时可显式重新评估", "evaluated_at": now}
                    atomic_json(record_path(root, tid), state)
                    counts["model_attempts"] += 1
                    result, usage = classifier(context, before_model=before_model)
                    ensure_scan_active()
                    if (not isinstance(result, dict) or set(result) != {"classification", "reason"}
                            or result["classification"] not in SCHEMA["properties"]["classification"]["enum"]
                            or not isinstance(result["reason"], str)):
                        raise ValueError("归档评估输出无效")
                    fresh = backend.read(tid)
                    fresh_info = activity(fresh)
                    if (protected(fresh, tid, cfg, guard_ids, root) or not fresh_info
                            or fresh_info[1] != fingerprint or backend.is_archived(tid)):
                        counts["stale"] += 1
                        continue
                    state.update(classification=result["classification"], reason=result["reason"][:200], usage=usage)
                    atomic_json(record_path(root, tid), state)
                if eligible(state.get("classification"), age, cfg):
                    candidates.append({"id": tid, "title": thread.get("name") or "",
                                       "fingerprint": fingerprint, "idle_days": int(age / DAY),
                                       "reason": state["reason"]})
                else:
                    counts["kept"] += 1
            except ModelSkipped as exc:
                if exc.status == "disabled":
                    stopped = True
                    break
                counts[exc.status] += 1
            except (BackendError, ValueError, OSError):
                counts["errors"] += 1
        report = {"status": "disabled" if stopped else "preview", "created_at": now,
                  "enabled": policy(root)["enabled"],
                  "counts": dict(counts), "candidates": [] if stopped else candidates}
        atomic_json(root / "archive/preview.json", report)
        return report


def check(backend, root, tid, current_id=None):
    """归档执行前复核；没有有效开关/缓存/保护判定时不放行。"""
    tid = valid_id(tid)
    now, cfg = time.time(), policy(root)
    if not cfg["enabled"]:
        return {"status": "disabled"}
    guard_ids = live_guards(root, current_id)
    state = read_json(record_path(root, tid))
    if state.get("archived_at") or state.get("protected") or backend.is_archived(tid):
        return {"status": "protected_or_archived"}
    thread = backend.read(tid)
    info = activity(thread)
    if protected(thread, tid, cfg, guard_ids, root) or info is None:
        return {"status": "protected"}
    stamp, fingerprint, _ = info
    if (state.get("context_version") != CONTEXT_VERSION or fingerprint != state.get("fingerprint")
            or not eligible(state.get("classification"), now - stamp, cfg)):
        return {"status": "not_eligible"}
    return {"status": "ready_to_archive", "id": tid, "title": thread.get("name") or ""}


def archive(backend, root, tid, current_id=None):
    """复核通过后写入归档时间戳并记录终态；归档不删除任何数据。"""
    verdict = check(backend, root, tid, current_id)
    if verdict.get("status") != "ready_to_archive":
        return verdict
    tid = verdict["id"]
    with thread_lock(root / "archive", "scan") as acquired:
        if not acquired:
            raise ValueError("归档扫描正在运行，稍后再试")
        backend.archive(tid)
        path = record_path(root, tid)
        state = read_json(path)
        state.setdefault("archived_at", time.time())
        atomic_json(path, state)
    return {"status": "archived", "id": tid, "title": verdict["title"]}


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="闲置话题归档：预览、复核与执行")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--live", action="store_true", help="允许独立模型评估新候选，消耗额度")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--scheduled", action="store_true", help="定时入口；归档开关关闭时不评估")
    p.add_argument("--current-id", default=None, help="当前会话 ID，始终保护")
    for name in ("check", "archive", "protect", "release"):
        sub.add_parser(name).add_argument("thread_id")
    for name in ("enable", "pause", "status"):
        sub.add_parser(name)
    args = parser.parse_args()
    root = data_dir()
    try:
        if args.command in ("enable", "pause", "status"):
            cfg = policy(root)
            if args.command != "status":
                cfg["enabled"] = args.command == "enable"
                if args.command == "pause":
                    cfg["pause_revision"] = time.time_ns()
                atomic_json(root / "archive/config.json", cfg)
            result = {"config": cfg, "data_dir": str(root / "archive")}
        elif args.command in ("protect", "release"):
            path = record_path(root, args.thread_id)
            with thread_lock(root / "archive", "scan") as acquired:
                if not acquired:
                    raise ValueError("归档扫描正在运行，稍后再试")
                state = read_json(path)
                if args.command == "protect":
                    state["protected"] = True
                else:
                    state = {}  # 只解除本插件记录；不恢复、不启动原任务。
                atomic_json(path, state)
            result = {"status": args.command}
        else:
            config = load_config(root)
            current_id = args.current_id if hasattr(args, "current_id") else None
            with ZCodeBackend() as backend:
                if args.command == "scan":
                    if not 0 <= args.limit <= 20:
                        raise ValueError("单次模型评估数量必须在 0～20 之间")
                    fn = (lambda context, **kw: classify(root, config, context, **kw)) if args.live else None
                    result = scan(backend, root, fn, args.limit,
                                  scheduled=args.scheduled, current_id=current_id)
                elif args.command == "check":
                    result = check(backend, root, args.thread_id, current_id)
                else:
                    result = archive(backend, root, args.thread_id, current_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (BackendError, ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
