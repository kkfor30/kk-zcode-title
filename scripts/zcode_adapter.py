"""ZCode 适配层：读取 SQLite 会话库并写入标题元数据；通过 HTTP 调用独立命名模型。

不创建会话、不发送消息、不修改对话内容；只 UPDATE session 表的标题字段。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class BackendError(RuntimeError):
    pass


class ModelSkipped(BackendError):
    """调用前发现状态已改变；不是模型失败，也不自动重试。"""
    def __init__(self, status):
        super().__init__(status)
        self.status = status


def process_options():
    # 隐藏后台子进程的控制台窗口；不通过 shell 执行模型参数。
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def worker_env() -> dict[str, str]:
    env = os.environ.copy()
    env["KK_ZCODE_TITLE_WORKER"] = "1"
    return env


def db_path() -> Path:
    override = os.environ.get("KK_ZCODE_TITLE_DB")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"


def v2_config_path() -> Path:
    return Path.home() / ".zcode" / "v2" / "config.json"


# ---------------------------------------------------------------------------
# 厂商检测与模型推荐
# ---------------------------------------------------------------------------

LIGHT_HINTS = ("flash", "turbo", "mini", "lite", "air", "nano")
SKIP_HINTS = ("expires", "vision", "-exp", "thinking", "opus", "audio", "image", "embed", "rerank")
SUPPORTED_KINDS = ("anthropic", "openai-compatible")


def pick_cheapest_model(models: list[str]) -> str | None:
    """启发式挑轻量档：优先 flash/turbo/mini 等命名，剔除实验/重型/多模态。"""
    scored = []
    for name in models:
        low = name.lower()
        if any(hint in low for hint in SKIP_HINTS):
            continue
        light = sum(low.count(hint) for hint in LIGHT_HINTS)
        scored.append((-light, len(name), name))
    if not scored:
        return None
    return min(scored)[2]


def detect_providers() -> tuple[list[dict], list[dict]]:
    """读取 ZCode 已接入的模型厂商。

    返回 (可用候选, 跳过项)。候选必须具备明文 apiKey、受支持的协议和模型列表；
    key 只在写入插件配置时使用，不进入任何输出。"""
    path = v2_config_path()
    if not path.exists():
        return [], [{"provider": "*", "reason": "未找到 ZCode 配置：" + str(path)}]
    try:
        providers = json.loads(path.read_text(encoding="utf-8")).get("provider", {})
    except (OSError, ValueError) as exc:
        return [], [{"provider": "*", "reason": f"ZCode 配置不可读：{exc}"}]
    usable, skipped = [], []
    for provider_id, cfg in providers.items():
        if not isinstance(cfg, dict):
            continue
        options = cfg.get("options") or {}
        api_key = options.get("apiKey") or ""
        base_url = options.get("baseURL") or ""
        kind = cfg.get("kind") or ""
        models = sorted((cfg.get("models") or {}).keys())
        reason = None
        if kind not in SUPPORTED_KINDS:
            reason = f"协议不支持（{kind or '未知'}）"
        elif not api_key:
            reason = "OAuth/套餐接入，无明文 API key"
        elif cfg.get("systemDisabledReason"):
            reason = f"ZCode 标记不可用（{cfg['systemDisabledReason']}）"
        elif not base_url.startswith(("http://", "https://")):
            reason = "缺少接口地址"
        elif not models:
            reason = "没有模型列表"
        if reason:
            skipped.append({"provider": provider_id, "name": cfg.get("name") or "", "reason": reason})
            continue
        usable.append({
            "provider": provider_id, "name": cfg.get("name") or provider_id,
            "kind": kind, "base_url": base_url.rstrip("/"), "api_key": api_key,
            "models": models, "picked_model": pick_cheapest_model(models),
        })
    return usable, skipped


# ---------------------------------------------------------------------------
# 统一聊天调用：按协议分发
# ---------------------------------------------------------------------------

def _urlopen(request, timeout):
    """系统代理不可达（如代理软件已退出）时自动回退直连。HTTP 业务错误不重试。

    首次失败时 ProxyHandler 已把 request 改写为指向代理（set_proxy 污染），
    因此回退必须重建干净的原始请求，否则仍会连向已死的代理端口。
    """
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        fresh = urllib.request.Request(
            request.full_url, data=request.data, method=request.get_method(),
            headers=dict(request.header_items()))
        return direct.open(fresh, timeout=timeout)


def _chat_openai(base_url, api_key, model, system, user_text, timeout) -> tuple[str, dict]:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user_text}],
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with _urlopen(request, timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 400 and "response_format" in detail:
            body.pop("response_format", None)
            request.data = json.dumps(body).encode("utf-8")
            with _urlopen(request, timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        else:
            raise BackendError(f"模型请求失败（HTTP {exc.code}）：{detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BackendError("模型网络错误或超时") from exc
    text = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return text, payload.get("usage", {}) or {}


def _chat_anthropic(base_url, api_key, model, system, user_text, timeout) -> tuple[str, dict]:
    # 思考型模型（GLM/DeepSeek）默认先输出 thinking 块；显式关闭并放宽预算，
    # 避免思考耗尽 max_tokens 导致 text 块为空。部分端点（智谱开放平台）不支持
    # 关闭思考、只接受 low/high/max 档位，被拒时自动降级为最低档。
    body = {
        "model": model, "max_tokens": 4000, "system": system,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": user_text}],
    }

    def send():
        request = urllib.request.Request(
            base_url.rstrip("/") + "/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with _urlopen(request, timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 400 and "思考" in detail and body["thinking"]["type"] != "low":
                body["thinking"] = {"type": "low"}
                return send()
            raise BackendError(f"模型请求失败（HTTP {exc.code}）：{detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BackendError("模型网络错误或超时") from exc

    payload = send()
    text = "".join(block.get("text", "") for block in payload.get("content", [])
                   if block.get("type") == "text")
    usage = payload.get("usage", {}) or {}
    return text, {"prompt_tokens": usage.get("input_tokens"),
                  "completion_tokens": usage.get("output_tokens")}


def chat(config, system, user_text, timeout) -> tuple[str, dict]:
    """按 provider_kind 分发；config 需含 model/base_url/api_key/provider_kind。"""
    if config.get("provider_kind") == "anthropic":
        return _chat_anthropic(config["base_url"], config["api_key"], config["model"],
                               system, user_text, timeout)
    return _chat_openai(config["base_url"], config["api_key"], config["model"],
                        system, user_text, timeout)


def test_model(provider: dict, model: str, timeout: float = 15) -> dict:
    """真实调用一次微型请求，验证 key、模型与协议可用。不写任何配置。"""
    probe = {**provider, "provider_kind": provider["kind"], "model": model}
    started = time.monotonic()
    text, usage = chat(probe, "你是连通性测试。只输出一个 JSON 对象：{\"ok\": true}", "ping", timeout)
    latency = int((time.monotonic() - started) * 1000)
    try:
        parse_model_json(text)
        parsed = True
    except ValueError:
        parsed = False
    return {"ok": bool(text.strip()), "json_reply": parsed,
            "latency_ms": latency, "chars": len(text)}


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = "file:" + urllib.parse.quote(str(path).replace("\\", "/")) + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


class ZCodeBackend:
    """直接读写 ZCode 会话库。读走只读连接；写用短事务并读回核验。"""

    def __init__(self, timeout: float = 15):
        self.timeout = timeout
        self._ro: sqlite3.Connection | None = None

    def __enter__(self):
        path = db_path()
        if not path.exists():
            raise BackendError(f"未找到 ZCode 会话库：{path}")
        self._ro = _ro_connect(path)
        return self

    def __exit__(self, *_):
        if self._ro is not None:
            self._ro.close()
            self._ro = None

    def read(self, session_id: str) -> dict:
        """组装为与原 Codex thread 相同形状：name/cwd/turns(id+items)。"""
        row = self._ro.execute(
            "SELECT title, directory, time_archived, parent_id FROM session WHERE id = ?",
            (session_id,)).fetchone()
        if row is None:
            raise BackendError("会话不存在：" + session_id)
        title, directory, archived, parent_id = row
        turns = self._read_turns(session_id)
        return {"id": session_id, "name": title or "", "cwd": directory or "",
                "archived": archived is not None, "parent_id": parent_id or "",
                "turns": turns}

    def list_sessions(self, *, archived: bool = False) -> list[dict]:
        """未归档（或已归档）会话的元数据清单；归档扫描用。"""
        condition = "time_archived IS NOT NULL" if archived else "time_archived IS NULL"
        rows = self._ro.execute(
            f"SELECT id, title, directory, parent_id FROM session WHERE {condition}").fetchall()
        return [{"id": r[0], "name": r[1] or "", "cwd": r[2] or "", "parent_id": r[3] or ""}
                for r in rows]

    def archive(self, session_id: str):
        """写入归档时间戳；短事务 + 读回核验，不改其他状态。"""
        conn = sqlite3.connect(db_path(), timeout=self.timeout)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE session SET time_archived = ? WHERE id = ? AND time_archived IS NULL",
                (int(time.time() * 1000), session_id))
            if cursor.rowcount != 1:
                conn.rollback()
                raise BackendError("会话不存在或已归档：" + session_id)
            conn.commit()
        finally:
            conn.close()
        if not self.is_archived(session_id):
            raise BackendError("归档写入后核验不一致")

    def _read_turns(self, session_id: str) -> list[dict]:
        messages = self._ro.execute(
            "SELECT id, sequence, data FROM message WHERE session_id = ? ORDER BY sequence",
            (session_id,)).fetchall()
        text_parts: dict[str, list] = {}
        for message_id, part_json in self._ro.execute(
                "SELECT message_id, data FROM part WHERE session_id = ? "
                "AND json_extract(data, '$.type') = 'text'", (session_id,)):
            part = json.loads(part_json)
            if part.get("text"):
                text_parts.setdefault(message_id, []).append(part)
        turns: list[dict] = []
        for message_id, sequence, message_json in messages:
            message = json.loads(message_json)
            role = message.get("role")
            semantics = message.get("semantics") or {}
            if role == "user":
                if semantics.get("origin") not in (None, "real_user"):
                    continue  # 过滤宿主注入的用户消息
                texts = [p["text"] for p in text_parts.get(message_id, [])]
                if not texts:
                    continue
                turns.append({
                    "id": str(sequence),
                    "items": [{"type": "userMessage",
                               "content": [{"type": "text", "text": t} for t in texts]}],
                })
            elif role == "assistant" and message.get("finish") == "stop" and turns:
                # 只保留每轮最终回答；中间 tool-calls 步骤不进入命名上下文。
                parts = text_parts.get(message_id, [])
                if not parts:
                    continue
                stamps = [p.get("time", {}).get("end") for p in parts if p.get("time")]
                item = {"type": "agentMessage", "text": "\n".join(p["text"] for p in parts),
                        "completed_at": max(stamps) if stamps else None}
                turns[-1]["items"] = [i for i in turns[-1]["items"] if i["type"] != "agentMessage"]
                turns[-1]["items"].append(item)
        return turns

    def rename(self, session_id: str, title: str):
        conn = sqlite3.connect(db_path(), timeout=self.timeout)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE session SET title = ?, title_source = ?, time_title_updated = ? "
                "WHERE id = ?",
                (title, "generated", int(time.time() * 1000), session_id))
            if cursor.rowcount != 1:
                conn.rollback()
                raise BackendError("会话不存在，标题未写入：" + session_id)
            conn.commit()
        finally:
            conn.close()
        verified = self.read(session_id)["name"]
        if verified != title:
            raise BackendError("标题写入后核验不一致")

    def is_archived(self, session_id: str) -> bool:
        row = self._ro.execute(
            "SELECT time_archived FROM session WHERE id = ?", (session_id,)).fetchone()
        return bool(row and row[0] is not None)


SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["keep", "rename"]},
        "title": {"type": "string"}, "reason": {"type": "string"},
    },
    "required": ["action", "title", "reason"],
}


def normalize_project_prefix(candidate, context):
    """去掉与外层目录精确等价的重复前缀，不猜项目别名或修改 keep。"""
    hint = re.sub(r"[\W_]+", "", context.get("project_hint", ""))
    if candidate.get("action") != "rename" or not hint or " " not in candidate.get("title", ""):
        return candidate
    emoji, body = candidate["title"].split(" ", 1)
    # 兼容 kite-lms、Kite LMS、KiteLMS，不把 Maple 错当成 MaplePay。
    pattern = r"^" + r"[\s._-]*".join(re.escape(c) for c in hint) + r"\s+(.+)$"
    match = re.match(pattern, body, re.IGNORECASE)
    if not match:
        return candidate
    remaining = match.group(1).strip()
    if len(remaining) < 2 or re.match(r"^(与|和|到|及|→|->|vs\b|to\b)", remaining, re.IGNORECASE):
        return candidate
    return {**candidate, "title": emoji + " " + remaining}


def parse_model_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# 模型优先级链：额度耗尽/故障时自动切换下一个厂商
# ---------------------------------------------------------------------------

PROVIDER_COOLDOWN_SECONDS = 30 * 60


def provider_chain(config) -> list[dict]:
    """返回按优先级排列的可用模型配置；健康的在前，冷却中的殿后。"""
    providers = config.get("providers") or []
    if not providers and all(config.get(k) for k in ("model", "base_url", "api_key")):
        providers = [{k: config[k] for k in ("model", "base_url", "api_key", "provider_kind")}]
    return providers


def _load_chain_state(state_dir) -> dict:
    path = Path(state_dir) / "providers-state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_chain_state(state_dir, state):
    path = Path(state_dir) / "providers-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mark_provider(state_dir, name, failed):
    entry = {"failed": failed, "time": time.time()}
    state = _load_chain_state(state_dir)
    state[name] = entry
    _save_chain_state(state_dir, state)


def ordered_providers(config, state_dir) -> list[dict]:
    """冷却中的厂商排到链尾兜底，避免每次都先打已知额度耗尽的厂商。"""
    providers = provider_chain(config)
    now = time.time()
    state = _load_chain_state(state_dir)

    def cooling(name):
        record = state.get(name or "", {})
        return bool(record.get("failed")
                    and now - record.get("time", 0) < PROVIDER_COOLDOWN_SECONDS)

    return sorted(providers, key=lambda p: cooling(p.get("name")))


def generate_json(config, context, policy, output_schema, *, before_model=None, state_dir=None):
    """隔离的无工具模型调用；按优先级链尝试，额度耗尽或故障自动切换。"""
    providers = ordered_providers(config, state_dir) if state_dir else provider_chain(config)
    if not providers:
        raise BackendError("命名模型未配置；请执行 setup 检测厂商并选择，"
                           "或 configure --model <模型> --base-url <地址> --api-key <密钥>")
    policy_text = Path(policy).read_text(encoding="utf-8") if isinstance(policy, (str, Path)) else policy
    system = policy_text + "\n\n只输出一个 JSON 对象，字段恰好为 action、title、reason；不要输出其他文本。"
    errors = []
    for provider in providers:
        label = provider.get("name") or provider.get("model")
        # 配额等待和每次内部重试之后，紧接真实模型请求前复核。
        if before_model:
            before_model()
        try:
            text, usage = chat(provider, system, json.dumps(context, ensure_ascii=False),
                               config["model_timeout_seconds"])
            result = parse_model_json(text)
        except BackendError as exc:
            errors.append(f"{label}：{exc}")
            if state_dir:
                mark_provider(state_dir, label, failed=True)
            continue
        if state_dir:
            mark_provider(state_dir, label, failed=False)
        return result, usage
    raise BackendError("；".join(errors) if errors else "命名模型链为空")


def _generate_title_once(config, context, plugin_root, *, before_model=None, state_dir=None):
    # 只有问候/确认时没有命名证据；确定性保留，避免模型凭空生成"普通讨论"。
    trivial = {"", "你好", "您好", "hi", "hello", "嗨", "谢谢", "好的", "好", "ok", "收到", "继续", "嗯"}
    user_texts = [context.get("original_goal", "")] + [
        message.get("text", "") for turn in context.get("recent_turns", [])
        for message in turn.get("messages", []) if message.get("role") == "user"
    ]
    if all(re.sub(r"[\W_]+", "", text).casefold() in trivial for text in user_texts):
        return {"action": "keep", "title": context.get("current_title", ""),
                "reason": "只有问候或确认，缺少新的命名依据"}, {}
    result, usage = generate_json(config, context, plugin_root / "prompts/naming.md", SCHEMA,
                                  before_model=before_model, state_dir=state_dir)
    return normalize_project_prefix(result, context), usage


def generate_title(config, context, plugin_root, *, before_model=None, state_dir=None):
    deadline = time.monotonic() + config.get("model_timeout_seconds", 100)
    candidate, usage = _generate_title_once(config, context, plugin_root,
                                            before_model=before_model, state_dir=state_dir)
    current = context.get("current_title", "")
    legacy = current.count("｜") != 1 or current.startswith("🛠")
    # 模型偶尔误把旧标题判断为结构合规。只复核一次，不自行猜对象或强制改名。
    # 问候过滤不调用模型且无 usage，仍然直接保留。
    remaining = deadline - time.monotonic()
    if candidate.get("action") == "keep" and legacy and usage and remaining > 0:
        # 格式复核共享首次生成的时间预算，不能使命名的最坏耗时翻倍。
        retry_config = {**config, "model_timeout_seconds": remaining}
        candidate, retry_usage = _generate_title_once(retry_config, {
            **context,
            "naming_feedback": "原标题尚未符合 emoji 对象｜目标结构，或仍使用旧开发图标。请重新核对：有明确对象和目标时只迁移格式，保留准确主线；只有依据不足时 keep。不要误称旧格式已合规。",
        }, plugin_root, before_model=before_model, state_dir=state_dir)
        usage = {key: usage.get(key, 0) + retry_usage.get(key, 0)
                 for key in usage.keys() | retry_usage.keys()}
    return candidate, usage
