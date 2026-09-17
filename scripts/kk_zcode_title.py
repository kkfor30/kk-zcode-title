#!/usr/bin/env python3
"""话题自动命名入口；Hook 始终只向宿主返回空 JSON。"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from zcode_adapter import (BackendError, ModelSkipped, ZCodeBackend, db_path,
                           detect_providers, generate_title, process_options,
                           test_model, trivial_user_text, worker_env)
import file_lock

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "enabled": True,
    "model": None,
    "base_url": None,
    "api_key": None,
    "provider_kind": "openai-compatible",
    "provider_name": None,
    "providers": [],
    "recent_turns": 5,
    "max_context_chars": 14000,
    "model_timeout_seconds": 100,
    "max_parallel_workers": 2,
}
EMOJI = ("🎬", "🔧", "🐛", "🚀", "📊", "🌐", "🔎", "🎨", "📝", "📅", "⚙️", "💬")
POLICY_VERSION = 8
EXCERPT_VERSION = 1
WORKER_RETRY_WAIT_SECONDS = float(os.environ.get("KK_ZCODE_TITLE_RETRY_WAIT", "10"))
HOOK_STDIN_TIMEOUT_SECONDS = float(os.environ.get("KK_ZCODE_TITLE_STDIN_TIMEOUT", "2"))
SETTLE_TIMEOUT_SECONDS = float(os.environ.get("KK_ZCODE_TITLE_SETTLE_TIMEOUT", "5"))
HOOK_SMOKE_SESSION = "sess_00000000-0000-4000-8000-000000000000"
BACKLOG_LIMIT_MAX = 20
VS16 = "\uFE0F"


def allowed_emoji_tokens():
    """允许的类别 emoji；⚙️ 带或不带变异选择符都算合法。"""
    tokens = []
    for emoji in EMOJI:
        tokens.append(emoji)
        if emoji.endswith(VS16):
            tokens.append(emoji[:-1])
        else:
            tokens.append(emoji + VS16)
    return tuple(dict.fromkeys(tokens))


ALLOWED_EMOJI = allowed_emoji_tokens()


def coerce_legacy_category_emoji(title):
    """旧开发图标只换类别，不改对象与目标，避免为此再打一次模型。"""
    if not isinstance(title, str) or " " not in title:
        return title
    emoji, body = title.split(" ", 1)
    base = emoji.replace(VS16, "")
    if base in ("🧩", "🛠"):
        return "🔧 " + body
    return title


def title_has_allowed_emoji(title):
    return any(title.startswith(token + " ") for token in ALLOWED_EMOJI)


def data_dir():
    override = os.environ.get("KK_ZCODE_TITLE_DATA")
    return Path(override).expanduser() if override else Path(
        os.environ.get("ZCODE_HOME", str(Path.home() / ".zcode"))
    ) / "kk-zcode-title"


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON 文件必须是对象")
    return value


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def load_config(root):
    config = DEFAULTS | read_json(root / "config.json")
    if not isinstance(config["enabled"], bool):
        raise ValueError("enabled 必须是布尔值")
    for key, lower, upper in (("recent_turns", 3, 5), ("max_context_chars", 3000, 20000),
                              ("model_timeout_seconds", 10, 110), ("max_parallel_workers", 1, 8)):
        if type(config[key]) is not int or not lower <= config[key] <= upper:
            raise ValueError(f"{key} 必须在 {lower}～{upper} 之间")
    for key in ("model", "base_url", "api_key", "provider_name"):
        if config[key] is not None and (not isinstance(config[key], str) or not config[key].strip()):
            raise ValueError(f"{key} 只能为 null 或非空字符串")
    if config["provider_kind"] not in ("openai-compatible", "anthropic"):
        raise ValueError("provider_kind 必须是 openai-compatible 或 anthropic")
    if not isinstance(config["providers"], list):
        raise ValueError("providers 必须是数组")
    for item in config["providers"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("name", "model", "base_url", "api_key")):
            raise ValueError("providers 每项需包含 name、model、base_url、api_key")
        if item.get("provider_kind") not in ("openai-compatible", "anthropic"):
            raise ValueError("providers 每项的 provider_kind 无效")
    return config


def valid_id(value):
    """校验会话标识尾部必须是 UUID；返回原始值以保持与会话库一致。"""
    raw = str(value)
    if not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", raw):
        raise ValueError("无效的会话标识")
    return raw


@contextmanager
def thread_lock(root, thread_id, wait_seconds=0):
    # 内核锁在进程结束后释放，避免崩溃留下永久锁或两个 Worker 覆盖结果。
    path = root / "locks" / (thread_id + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                file_lock.acquire(stream)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        try:
            yield True
        finally:
            file_lock.release(stream)


@contextmanager
def worker_slot(root, limit, wait_seconds):
    """不同话题共享进程池配额，等待时间算入模型预算。"""
    deadline = time.monotonic() + wait_seconds
    while True:
        for index in range(limit):
            with thread_lock(root / "worker-pool", str(index)) as acquired:
                if acquired:
                    yield True
                    return
        if time.monotonic() >= deadline:
            yield False
            return
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))


def limited_title(root, config, context, *, before_model=None):
    deadline = time.monotonic() + config["model_timeout_seconds"]
    with worker_slot(root, config["max_parallel_workers"], config["model_timeout_seconds"]) as acquired:
        remaining = deadline - time.monotonic()
        if not acquired or remaining <= 0:
            raise BackendError("后台命名并发已满；本次保留原标题")
        return generate_title({**config, "model_timeout_seconds": remaining}, context, ROOT,
                              before_model=before_model, state_dir=root)


def ensure_title_active(backend, thread_id, root):
    if backend.is_archived(thread_id):
        raise ModelSkipped("archived")
    if not load_config(root)["enabled"]:
        raise ModelSkipped("disabled")
    if read_json(state_path(root, thread_id)).get("locked"):
        raise ModelSkipped("locked")


def read_settled_thread(backend, thread_id, event_turn, timeout=None):
    """确认事件轮次已完成并落库；持久化略有延迟时短暂轮询。

    event_turn 为 "latest" 时以读取到的最后一轮为事件轮次（Stop 触发时
    最后一轮即事件轮次）；否则与轮次序号比对，之后的新轮次使事件过期。
    """
    deadline = time.monotonic() + (SETTLE_TIMEOUT_SECONDS if timeout is None else timeout)
    while True:
        thread = backend.read(thread_id)
        turns = thread.get("turns", [])
        if not turns:
            return thread, "empty"
        if event_turn != "latest" and turns[-1]["id"] != event_turn:
            return thread, "outdated_event"
        if any(item["type"] == "agentMessage" for item in turns[-1]["items"]):
            return thread, None
        if time.monotonic() >= deadline:
            return thread, "turn_not_settled"
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def state_path(root, thread_id):
    return root / "threads" / (thread_id + ".json")


def audit(root, thread_id, result):
    path = root / "logs" / (thread_id + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 256 * 1024:
        os.replace(path, path.with_suffix(".previous.jsonl"))
    # 不保存对话原文、模型提示词、推理或 CLI 原始 stderr。
    entry = {"time": int(time.time()), **result}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def clean_text(text):
    # 剔除宿主注入的浏览器状态，保留真实用户请求。
    text = re.sub(r"<in-app-browser-context\b[^>]*>[\s\S]*?</in-app-browser-context>", "", text)
    text = re.sub(r"<environment_context>[\s\S]*?</environment_context>", "", text)
    for tag in ("recommended_plugins", "skills_instructions", "app-context", "skill"):
        text = re.sub(r"<" + tag + r"\b[^>]*>[\s\S]*?</" + tag + r">", "", text)
    # 附件说明和能力清单常出现在真实请求前，不能占满每条消息的摘录预算。
    request = re.search(r"(?m)^#{1,3} My request:\s*\n", text)
    if request:
        text = text[request.end():]
    return text.strip()


def project_hint(thread):
    cwd = thread.get("cwd")
    if not cwd:
        return ""
    path = Path(cwd)
    if path == Path.home() or path.parent.name.lower() in ("users", "home"):
        return ""
    name = path.name
    if name.lower() in ("desktop", "documents", "downloads", "tmp", "project", "projects"):
        return ""
    return name[:64] if re.fullmatch(r"[\w .-]{1,64}", name) else ""


def conflicting_titles(root, thread_id, candidate, scope_key=""):
    conflicts = set()
    for path in (root / "threads").glob("*.json"):
        if path.stem == thread_id:
            continue
        try:
            state = read_json(path)
        except (ValueError, OSError):
            continue
        if state.get("scope_key", "") != scope_key:
            continue
        other = state.get("last_seen_title")
        if other == candidate:
            conflicts.add(other)
    return sorted(conflicts)


def item_text(item):
    if item.get("type") == "userMessage":
        return clean_text("\n".join(
            part.get("text", "") for part in item.get("content", []) if part.get("type") == "text"
        ))
    return clean_text(item.get("text", ""))


def snapshot(thread, config):
    """只给命名模型用户与最终回答；用最新轮次 ID 检测生成期间的新活动。"""
    turns = thread.get("turns", [])
    effective = []
    for turn in turns:
        messages = []
        for item in turn.get("items", []):
            kind = item.get("type")
            if kind != "userMessage" and not (
                kind == "agentMessage" and item.get("phase") in (None, "final_answer")
            ):
                continue
            text = item_text(item)
            if text:
                messages.append({"role": "user" if kind == "userMessage" else "assistant", "text": text})
        if any(m["role"] == "user" for m in messages):
            effective.append({"id": turn["id"], "messages": messages})
    title = thread.get("name") or ""
    selected = effective[-config["recent_turns"]:]
    budget = config["max_context_chars"]
    # 为每轮的用户目标保留空间；助手长回答不能挤掉其他轮。
    per_message = max(200, (budget - 2000) // max(1, sum(len(t["messages"]) for t in selected)))
    recent = [{"id": t["id"], "messages": [
        {"role": m["role"], "text": m["text"][:min(per_message, 1200 if m["role"] == "user" else 500)]}
        for m in t["messages"]
    ]} for t in selected]
    original = ""
    if effective:
        original = next(m["text"] for m in effective[0]["messages"] if m["role"] == "user")[:800]
    latest_id = turns[-1]["id"] if turns else None
    context = {"current_title": title, "project_hint": project_hint(thread),
               "original_goal": original, "recent_turns": recent}
    signature = json.dumps({"project_hint": context["project_hint"],
                           "latest_id": latest_id, "effective": effective[-config["recent_turns"]:]},
                           ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(signature.encode()).hexdigest()
    scope_key = hashlib.sha256(str(thread["cwd"]).encode()).hexdigest() if thread.get("cwd") else ""
    return {"title": title, "latest_id": latest_id, "fingerprint": fingerprint,
            "context": context, "has_messages": bool(effective), "scope_key": scope_key,
            "excerpt_version": EXCERPT_VERSION, "title_source": thread.get("title_source") or ""}


def validate_candidate(candidate, current_title):
    if not isinstance(candidate, dict) or set(candidate) != {"action", "title", "reason"}:
        raise ValueError("模型输出字段无效")
    if candidate["action"] not in ("rename", "keep") or not all(
        isinstance(candidate[k], str) for k in ("title", "reason")
    ):
        raise ValueError("模型输出类型无效")
    if candidate["action"] == "keep":
        candidate = {**candidate, "title": current_title}
    else:
        title = coerce_legacy_category_emoji(candidate["title"])
        if title != title.strip() or not 4 <= len(title) <= 48:
            raise ValueError("标题长度或空白无效")
        if not title_has_allowed_emoji(title):
            raise ValueError("标题缺少允许的类别 emoji")
        body = title.split(" ", 1)[1]
        candidate = {**candidate, "title": title}
        if body.count("｜") != 1 or "|" in body:
            raise ValueError("标题必须采用对象｜目标结构")
        if any(not part or part != part.strip() for part in body.split("｜")):
            raise ValueError("标题对象与目标不能为空或带边缘空格")
        if (not body.strip() or any(e in body for e in EMOJI)
                or any(0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF for c in body)):
            raise ValueError("标题正文无效或包含多个类别 emoji")
        if any(unicodedata.category(c).startswith("C") for c in title):
            raise ValueError("标题含控制字符")
        if re.search(r"[A-Za-z]:[\\/]|\\\\", title):
            raise ValueError("标题含 Windows 绝对路径")
        if any(x in title for x in ("\n", "\r", "`", "https://", "http://", "@", "/Users/", "sk-")):
            raise ValueError("标题含不允许的格式或私人信息")
    return {**candidate, "reason": candidate["reason"][:300]}


def title_compliant(title):
    if not title:
        return False
    try:
        validate_candidate({"action": "rename", "title": title, "reason": "check"}, title)
        return True
    except ValueError:
        return False


def latest_user_is_trivial(context):
    texts = [
        message.get("text", "")
        for turn in context.get("recent_turns", [])
        for message in turn.get("messages", [])
        if message.get("role") == "user"
    ]
    return (not texts) or trivial_user_text(texts[-1])


def remember_fingerprint(path, state, before, extra=None):
    state.update(last_fingerprint=before["fingerprint"], excerpt_version=EXCERPT_VERSION,
                 policy_version=POLICY_VERSION, last_seen_title=before["title"],
                 last_turn_id=before["latest_id"], scope_key=before["scope_key"],
                 updated_at=int(time.time()))
    if extra:
        state.update(extra)
    atomic_json(path, state)


def process_thread(backend, generator, thread_id, root, config, *, apply=False, event_turn=None):
    thread_id = valid_id(thread_id)
    if not config["enabled"]:
        return {"status": "disabled"}
    # 新轮次的 Hook 等待旧 Worker 释放锁，再判断是否已经过期，避免丢掉最新请求。
    with thread_lock(root, thread_id, config["model_timeout_seconds"] * 2 + 20 if event_turn else 0) as acquired:
        if not acquired:
            return {"status": "busy"}
        path = state_path(root, thread_id)
        state = read_json(path)
        if backend.is_archived(thread_id):
            return {"status": "archived"}
        if event_turn:
            thread, pending = read_settled_thread(backend, thread_id, event_turn)
            if pending:
                return {"status": pending}
        else:
            thread = backend.read(thread_id)
        before = snapshot(thread, config)
        if not before["has_messages"]:
            return {"status": "empty"}
        if (thread.get("title_source") or before.get("title_source")) == "custom":
            return {"status": "manual_title", "title": before["title"]}
        # 上次写入后进程被中断时，先核对待确认结果，避免误认作手工改名。
        if state.get("pending_title") == before["title"]:
            state.update(last_seen_title=before["title"], last_generated_title=before["title"])
            state.pop("pending_title", None)
            if apply:
                atomic_json(path, state)
        # 初次观察到的标题可能仍是宿主的临时标题。只有成功评估/写入后，
        # 才有稳定基线可用于保护外部改名；过期结果不能建立这条基线。
        established = bool(state.get("last_fingerprint") or state.get("last_generated_title"))
        if (state.get("locked") and state.get("lock_reason") == "检测到外部改名"
                and not established):
            state.update(locked=False, lock_reason="首次标题尚未建立稳定基线")
            if apply:
                atomic_json(path, state)
                audit(root, thread_id, {"status": "initial_baseline_recovered"})
        if state.get("locked"):
            return {"status": "locked", "title": before["title"]}
        if established and "last_seen_title" in state and state["last_seen_title"] != before["title"]:
            if apply:
                state.update(locked=True, lock_reason="检测到外部改名", last_seen_title=before["title"])
                atomic_json(path, state)
            return {"status": "manual_title", "title": before["title"]}
        if state.get("last_fingerprint") == before["fingerprint"]:
            return {"status": "unchanged", "title": before["title"]}
        if title_compliant(before["title"]) and state.get("excerpt_version") != EXCERPT_VERSION:
            if apply:
                remember_fingerprint(path, state, before)
            return {"status": "unchanged", "title": before["title"]}
        if title_compliant(before["title"]) and latest_user_is_trivial(before["context"]):
            if apply:
                remember_fingerprint(path, state, before)
                audit(root, thread_id, {"status": "kept", "action": "keep",
                                        "title": before["title"], "usage": {}})
            return {"status": "kept", "action": "keep", "title": before["title"],
                    "reason": "标题已合规，最近一轮只是问候或确认", "usage": {}}
        try:
            ensure_title_active(backend, thread_id, root)
            candidate, usage = generator(before["context"])
        except ModelSkipped as exc:
            return {"status": exc.status}
        candidate = validate_candidate(candidate, before["title"])
        conflicts = conflicting_titles(root, thread_id, candidate["title"], before["scope_key"])
        if candidate["action"] == "rename" and conflicts:
            try:
                ensure_title_active(backend, thread_id, root)
                candidate, retry_usage = generator({**before["context"], "conflicting_titles": conflicts,
                    "naming_feedback": "候选与已记录任务重名。用对话里真实的项目、模块或内容主题区分；无法区分就保留原名，不编造编号。"})
            except ModelSkipped as exc:
                return {"status": exc.status, "usage": usage}
            candidate = validate_candidate(candidate, before["title"])
            usage = {key: usage.get(key, 0) + retry_usage.get(key, 0)
                     for key in usage.keys() | retry_usage.keys()}
            if candidate["action"] == "rename" and conflicting_titles(root, thread_id, candidate["title"], before["scope_key"]):
                return {"status": "ambiguous_title", "title": before["title"], "usage": usage}
        result = {"status": "preview", **candidate, "usage": usage}
        if not apply:
            return result
        # 模型运行期间用户可能发起下一轮、改名、暂停或锁定。
        fresh_config = load_config(root)
        if not fresh_config["enabled"]:
            return {"status": "disabled"}
        latest_state = read_json(path)
        if latest_state.get("locked"):
            return {"status": "locked"}
        if backend.is_archived(thread_id):
            return {"status": "archived"}
        after = snapshot(backend.read(thread_id), config)
        if after["title"] != before["title"] or after["fingerprint"] != before["fingerprint"]:
            return {"status": "stale_result"}
        state.update(last_seen_title=before["title"], last_turn_id=before["latest_id"],
                     scope_key=before["scope_key"], excerpt_version=EXCERPT_VERSION,
                     policy_version=POLICY_VERSION, updated_at=int(time.time()))
        if candidate["action"] == "rename" and candidate["title"] != before["title"]:
            state["pending_title"] = candidate["title"]
            atomic_json(path, state)
            try:
                backend.rename(thread_id, candidate["title"])
            except BackendError:
                # 网络/进程错误可能发生在写入成功后，先读回确认，不盲目重试。
                if snapshot(backend.read(thread_id), config)["title"] != candidate["title"]:
                    raise
            verified = snapshot(backend.read(thread_id), config)
            if verified["title"] != candidate["title"]:
                raise BackendError("标题写入后核验不一致")
            state.update(last_seen_title=candidate["title"], last_generated_title=candidate["title"])
            state.pop("pending_title", None)
            result["status"] = "renamed"
            result["verification"] = "metadata_only"
        else:
            result["status"] = "kept"
        state["last_fingerprint"] = before["fingerprint"]
        atomic_json(path, state)
        audit(root, thread_id, result)
        return result


def hook_python_command(hooks_file):
    try:
        data = json.loads(hooks_file.read_text(encoding="utf-8"))
        for group in data.get("hooks", {}).get("Stop", []):
            for hook in group.get("hooks", []):
                if hook.get("type") == "process" and hook.get("command"):
                    return str(hook["command"])
    except (OSError, ValueError):
        return None
    return None


def python_command_available(command):
    if not command:
        return False
    path = Path(command)
    if path.is_file():
        return True
    return shutil.which(command) is not None


def last_hook_audit(root):
    path = root / "logs" / "hook.jsonl"
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def hook_registration_state(root=None):
    """检查插件是否已注册并启用；只读配置，不修改状态。"""
    plugins_dir = Path.home() / ".zcode" / "cli" / "plugins"
    registered = None
    try:
        registry = json.loads((plugins_dir / "installed_plugins.json").read_text(encoding="utf-8"))
        for plugin in registry.get("plugins", []):
            if plugin.get("name") == "kk-zcode-title":
                registered = plugin.get("installPath")
    except (OSError, ValueError):
        return {"status": "registry_unreadable"}
    if registered is None:
        return {"status": "not_installed"}
    enabled = False
    try:
        config = json.loads((Path.home() / ".zcode" / "cli" / "config.json").read_text(encoding="utf-8"))
        enabled = config.get("plugins", {}).get("enabledPlugins", {}).get("kk-zcode-title@local") is True
    except (OSError, ValueError):
        pass
    hooks_file = Path(registered) / "hooks" / "hooks.json"
    command = hook_python_command(hooks_file) if hooks_file.exists() else None
    python_ok = python_command_available(command)
    audit_entry = last_hook_audit(root) if root is not None else None
    if not enabled or not hooks_file.exists():
        status = "registered_disabled"
    elif not python_ok:
        status = "python_not_found"
    else:
        status = "ready"
    return {"status": status, "install_path": registered, "hooks_json": hooks_file.exists(),
            "python_command": command, "python_available": python_ok,
            "last_hook_audit": audit_entry.get("status") if audit_entry else None,
            "last_hook_time": audit_entry.get("time") if audit_entry else None}


def redact_config(config):
    """输出给终端/对话的配置视图；密钥一律脱敏。"""
    return {**config, "api_key": "***" if config["api_key"] else None,
            "providers": [{**p, "api_key": "***"} for p in config["providers"]]}


def smoke_hook_entry():
    """在临时数据目录跑一次 Hook：必须秒回 {}，不打模型、不碰用户会话库。"""
    with tempfile.TemporaryDirectory(prefix="kk-zcode-title-smoke-") as tmp:
        env = os.environ.copy()
        env["KK_ZCODE_TITLE_DATA"] = tmp
        env["KK_ZCODE_TITLE_DB"] = str(Path(tmp) / "missing.sqlite")
        env.pop("KK_ZCODE_TITLE_WORKER", None)
        payload = json.dumps({
            "hook_event_name": "Stop",
            "session_id": HOOK_SMOKE_SESSION,
        })
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "hook"],
                input=payload, capture_output=True, timeout=5, env=env,
                cwd=str(ROOT), text=True, encoding="utf-8",
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "stdout": "", "elapsed_ms": 5000}
        elapsed_ms = int((time.monotonic() - started) * 1000)
        stdout = (proc.stdout or "").strip()
        return {"ok": stdout == "{}" and proc.returncode == 0, "stdout": stdout,
                "returncode": proc.returncode, "elapsed_ms": elapsed_ms}


def doctor(root, config, thread_id=None):
    hook = hook_registration_state(root)
    smoke = smoke_hook_entry()
    if hook.get("status") == "ready" and not smoke["ok"]:
        hook = {**hook, "status": "hook_smoke_failed"}
    hook["smoke"] = smoke
    output = {"python": sys.version.split()[0], "config": redact_config(config),
              "data_dir": str(root), "db": str(db_path()), "db_status": "unknown",
              "model_configured": bool(config["providers"]) or all(
                  config.get(k) for k in ("model", "base_url", "api_key")),
              "hook": hook}
    try:
        with ZCodeBackend() as backend:
            output["db_status"] = "ok"
            if thread_id:
                thread = backend.read(valid_id(thread_id))
                snap = snapshot(thread, config)
                output["thread"] = {k: snap[k] for k in ("title", "latest_id", "has_messages")}
    except BackendError as exc:
        output["db_status"] = f"error: {exc}"
    return output


def run_setup(root, args):
    """检测 ZCode 已接入厂商并测试推荐模型；--use 验证通过后按优先级写入配置。

    检测模式对每个厂商的推荐模型真实调用一次微型请求；输出不含 API key。
    --use 可重复出现，按出现顺序构成 fallback 链（前者额度耗尽自动切后者）。
    """
    usable, skipped = detect_providers()
    if not args.use:
        detected = []
        for provider in usable:
            entry = {k: provider[k] for k in ("provider", "name", "kind", "picked_model")}
            entry["models"] = provider["models"]
            if provider["picked_model"]:
                try:
                    entry["test"] = test_model(provider, provider["picked_model"])
                except BackendError as exc:
                    entry["test"] = {"ok": False, "error": str(exc)[:200]}
            else:
                entry["test"] = {"ok": False, "error": "无轻量档模型，需手动指定"}
            detected.append(entry)
        return {"usage": "setup --use <厂商> --use <厂商2> 按优先级写入；--model 覆盖首选模型",
                "detected": detected, "skipped": skipped}
    if len(args.use) > 1 and args.model:
        raise BackendError("--model 只能与单个 --use 连用；多厂商请分别使用各自推荐模型")
    chain, tests = [], []
    for use in args.use:
        provider = next((p for p in usable if use in (p["provider"], p["name"])), None)
        if provider is None:
            raise BackendError(f"未检测到可用厂商「{use}」；先执行 setup 查看列表")
        model = args.model or provider["picked_model"]
        if not model:
            raise BackendError(f"厂商「{provider['name']}」没有可自动推荐的模型，请用 --model 指定")
        if model not in provider["models"]:
            raise BackendError(f"模型 {model} 不在厂商「{provider['name']}」的模型列表中")
        result = test_model(provider, model)
        if not result["ok"]:
            raise BackendError(f"模型 {model} 测试失败（{provider['name']}），配置未写入")
        chain.append({"name": provider["name"], "model": model,
                      "base_url": provider["base_url"], "api_key": provider["api_key"],
                      "provider_kind": provider["kind"]})
        tests.append({"provider": provider["name"], "model": model, "test": result})
    config_path = root / "config.json"
    changes = read_json(config_path)
    changes["providers"] = chain
    first = chain[0]
    changes.update(model=first["model"], base_url=first["base_url"], api_key=first["api_key"],
                   provider_kind=first["provider_kind"], provider_name=first["name"])
    atomic_json(config_path, changes)
    return {"status": "configured", "priority": [f'{c["name"]}（{c["model"]}）' for c in chain],
            "note": "前者额度耗尽或失败时自动切换后者", "tests": tests}


def is_subagent_session(meta):
    tid = str(meta.get("id") or "")
    return bool(meta.get("parent_id")) or "subagent" in tid


def project_label(cwd):
    if not cwd:
        return ""
    name = Path(cwd).name
    return name[:64] if name else ""


def backlog_candidates(backend, root, *, current_id=None, limit=20):
    """本地筛选不合规主会话；不调用模型。"""
    skipped = Counter()
    candidates = []
    current_id = valid_id(current_id) if current_id else None
    for meta in backend.list_sessions(archived=False):
        tid = str(meta.get("id") or "")
        try:
            valid_id(tid)
        except ValueError:
            skipped["invalid_id"] += 1
            continue
        if current_id and tid == current_id:
            skipped["current"] += 1
            continue
        if is_subagent_session(meta):
            skipped["subagent"] += 1
            continue
        if (meta.get("title_source") or "") == "custom":
            skipped["custom"] += 1
            continue
        if read_json(state_path(root, tid)).get("locked"):
            skipped["locked"] += 1
            continue
        title = meta.get("name") or ""
        if trivial_user_text(title):
            skipped["trivial"] += 1
            continue
        if title_compliant(title):
            skipped["already_formatted"] += 1
            continue
        candidates.append({"id": tid, "title": title, "project": project_label(meta.get("cwd"))})
        if len(candidates) >= limit:
            break
    return {"status": "preview", "limit": limit, "candidates": candidates,
            "skipped": dict(skipped), "count": len(candidates)}


def run_backlog(backend, root, config, *, apply=False, current_id=None, limit=20):
    report = backlog_candidates(backend, root, current_id=current_id, limit=limit)
    if not apply:
        return report
    results = []
    for item in report["candidates"]:
        outcome = process_thread(
            backend, lambda context: limited_title(root, config, context),
            item["id"], root, config, apply=True,
        )
        results.append({"id": item["id"], "old": item["title"],
                        "status": outcome.get("status"), "title": outcome.get("title"),
                        "usage": outcome.get("usage") or {}})
    counts = Counter(row["status"] for row in results)
    return {"status": "applied", "limit": limit, "counts": dict(counts),
            "skipped": report["skipped"], "results": results}


def spawn_worker(session_raw):
    """派生独立后台进程执行命名；Hook 入口立即返回，不阻塞对话。"""
    args = [sys.executable, str(Path(__file__).resolve()), "worker", valid_id(session_raw)]
    options = {"env": worker_env(), "stdin": subprocess.DEVNULL,
               "stdout": subprocess.DEVNULL,
               "cwd": str(ROOT)}
    debug = os.environ.get("KK_ZCODE_TITLE_DEBUG")
    if debug:
        options["stderr"] = open(os.path.expanduser(debug), "a", encoding="utf-8")
    else:
        options["stderr"] = subprocess.DEVNULL
    if sys.platform == "win32":
        # DETACHED_PROCESS=0x8；CREATE_NO_WINDOW 避免桌面弹出控制台。
        flags = process_options().get("creationflags", 0)
        options["creationflags"] = flags | 0x00000008 | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    subprocess.Popen(args, **options)


def read_hook_stdin(max_bytes=1024 * 1024, timeout=HOOK_STDIN_TIMEOUT_SECONDS):
    """有界读取 Hook stdin。宿主若不关闭管道，超时后仍可用环境变量里的会话 ID。"""
    try:
        if sys.stdin.closed or sys.stdin.isatty():
            return ""
    except Exception:
        return ""
    chunks = []
    done = threading.Event()

    def _read():
        try:
            chunks.append(sys.stdin.read(max_bytes))
        except Exception:
            chunks.append("")
        finally:
            done.set()

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    done.wait(timeout)
    return chunks[0] if chunks else ""


def hook_session_id(event):
    raw = (event.get("session_id") or event.get("sessionId")
           or os.environ.get("CLAUDE_SESSION_ID")
           or os.environ.get("ZCODE_SESSION_ID")
           or os.environ.get("CLAUDE_CODE_SESSION_ID"))
    return raw if isinstance(raw, str) and raw.strip() else None


def hook_event_is_stop(event):
    name = event.get("hook_event_name") or event.get("hookEventName")
    return name in (None, "Stop")


def hook_stop_already_active(event):
    return bool(event.get("stop_hook_active") or event.get("stopHookActive"))


def main():
    # Hook 事件使用 UTF-8；不能依赖 Windows 当前代码页解释中文内容。
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="独立模型驱动的 ZCode 话题命名")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook", help="读取 Stop Hook stdin；派生 Worker 后立即返回空 JSON")
    p = sub.add_parser("worker", help=argparse.SUPPRESS)  # Hook 派生的后台进程入口
    p.add_argument("thread_id")
    p = sub.add_parser("doctor", help="只读检查运行环境")
    p.add_argument("--thread")
    sub.add_parser("status", help="显示配置和本地记录数量")
    sub.add_parser("pause", help="暂停自动命名")
    sub.add_parser("resume", help="恢复自动命名")
    p = sub.add_parser("configure", help="配置独立命名模型（OpenAI 兼容接口）")
    p.add_argument("--model")
    p.add_argument("--base-url")
    p.add_argument("--api-key")
    p = sub.add_parser("setup", help="检测 ZCode 已接入的模型厂商，测试推荐模型")
    p.add_argument("--use", metavar="厂商", action="append",
                   help="选定厂商（ID 或名称），可重复按优先级组成 fallback 链")
    p.add_argument("--model", metavar="模型", help="覆盖推荐模型（与单个 --use 连用）")
    for name in ("rename", "lock", "unlock"):
        p = sub.add_parser(name)
        p.add_argument("thread_id")
        if name == "rename":
            p.add_argument("--apply", action="store_true", help="写入；省略时只预览")
    p = sub.add_parser("backlog", help="预览或补齐不合规的历史主会话标题")
    p.add_argument("--apply", action="store_true", help="写入；省略时只列出候选")
    p.add_argument("--limit", type=int, default=20, help="单次最多处理条数，1～20")
    p.add_argument("--current-id", default=None, help="当前会话 ID，始终跳过")
    args = parser.parse_args()
    root = data_dir()
    is_hook = args.command == "hook"
    thread_id = None
    try:
        if sys.version_info < (3, 10):
            raise BackendError("需要 Python 3.10 或更新版本")
        config = load_config(root)
        if is_hook:
            if os.environ.get("KK_ZCODE_TITLE_WORKER") == "1" or not config["enabled"]:
                return 0
            raw = read_hook_stdin()
            try:
                event = json.loads(raw) if raw.strip() else {}
            except ValueError:
                event = {}
            if not isinstance(event, dict):
                event = {}
            if not hook_event_is_stop(event) or hook_stop_already_active(event):
                return 0
            # 记录原始事件供诊断；不含对话内容。
            audit(root, "hook", {"status": "event_received",
                                 "event_keys": sorted(event.keys()),
                                 "has_session_id": bool(hook_session_id(event))})
            session_raw = hook_session_id(event)
            if not session_raw:
                audit(root, "hook", {"status": "error", "error_type": "missing_session_id"})
                return 0
            spawn_worker(session_raw)
            return 0
        if args.command in ("pause", "resume", "configure"):
            config_path = root / "config.json"
            changes = read_json(config_path)
            if args.command in ("pause", "resume"):
                changes["enabled"] = args.command == "resume"
            else:
                if args.model:
                    changes["model"] = args.model
                if args.base_url:
                    changes["base_url"] = args.base_url.rstrip("/")
                if args.api_key:
                    changes["api_key"] = args.api_key
            atomic_json(config_path, changes)
            print(json.dumps(redact_config(load_config(root)), ensure_ascii=False))
            return 0
        if args.command == "status":
            print(json.dumps({"config": redact_config(config), "data_dir": str(root),
                              "tracked_threads": len(list((root / "threads").glob("*.json")))},
                             ensure_ascii=False))
            return 0
        if args.command == "setup":
            result = run_setup(root, args)
            if result is not None:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            result = doctor(root, config, args.thread)
        elif args.command == "backlog":
            if not 1 <= args.limit <= BACKLOG_LIMIT_MAX:
                raise ValueError(f"单次补齐数量必须在 1～{BACKLOG_LIMIT_MAX} 之间")
            current_id = args.current_id or os.environ.get("ZCODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
            with ZCodeBackend() as backend:
                result = run_backlog(backend, root, config, apply=args.apply,
                                     current_id=current_id, limit=args.limit)
        else:
            thread_id = thread_id or valid_id(args.thread_id)
            with ZCodeBackend() as backend:
                if args.command in ("lock", "unlock"):
                    with thread_lock(root, thread_id) as acquired:
                        if not acquired:
                            raise BackendError("该话题正在命名，稍后再试")
                        path = state_path(root, thread_id)
                        state = read_json(path)
                        state.update(locked=args.command == "lock", lock_reason="用户设置",
                                     last_seen_title=backend.read(thread_id).get("name") or "")
                        state.pop("last_fingerprint", None)
                        state.pop("pending_title", None)
                        atomic_json(path, state)
                        result = {"status": args.command, "title": state["last_seen_title"]}
                else:
                    is_worker = args.command == "worker"
                    result = process_thread(
                        backend, lambda context: limited_title(root, config, context,
                            before_model=lambda: ensure_title_active(backend, thread_id, root)),
                        thread_id, root, config, apply=is_worker or args.apply,
                        event_turn="latest" if is_worker else None,
                    )
                    # Stop 发出后宿主可能仍在落库；过期或未完成轮次各再读一次。
                    if is_worker and result["status"] in ("stale_result", "turn_not_settled"):
                        time.sleep(WORKER_RETRY_WAIT_SECONDS)
                        result = process_thread(
                            backend, lambda context: limited_title(root, config, context,
                                before_model=lambda: ensure_title_active(backend, thread_id, root)),
                            thread_id, root, config, apply=True, event_turn="latest",
                        )
                    if is_worker and result["status"] not in ("renamed", "kept"):
                        audit(root, thread_id, result)
        if args.command != "worker":
            print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        import traceback
        error = {"status": "error", "error_type": type(exc).__name__}
        if os.environ.get("KK_ZCODE_TITLE_DEBUG"):
            traceback.print_exc()
        if is_hook or args.command == "worker":
            # Hook 与 Worker 的输出不进对话，错误只写入审计日志。
            try:
                audit(root, thread_id or getattr(args, "thread_id", None) or "hook", error)
            except Exception:
                pass
            return 0
        message = str(exc) if isinstance(exc, (BackendError, ValueError)) else "操作失败；检查输入及本地配置"
        print(json.dumps({**error, "message": message}, ensure_ascii=False))
        return 1
    finally:
        if is_hook:
            print("{}")


if __name__ == "__main__":
    raise SystemExit(main())
