"""离线测试辅助：临时会话库与假后端。不调用外部模型。"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCHEMA_SQL = """
CREATE TABLE session (
  id TEXT PRIMARY KEY,
  project_id TEXT DEFAULT '',
  slug TEXT DEFAULT '',
  directory TEXT DEFAULT '',
  title TEXT DEFAULT '',
  version TEXT DEFAULT '1',
  time_created INTEGER DEFAULT 0,
  time_updated INTEGER DEFAULT 0,
  time_archived INTEGER,
  task_type TEXT DEFAULT 'interactive',
  title_source TEXT DEFAULT 'first_input',
  parent_id TEXT,
  time_title_updated INTEGER
);
CREATE TABLE message (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  time_created INTEGER DEFAULT 0,
  time_updated INTEGER DEFAULT 0,
  data TEXT,
  sequence INTEGER
);
CREATE TABLE part (
  id TEXT PRIMARY KEY,
  message_id TEXT,
  session_id TEXT,
  time_created INTEGER DEFAULT 0,
  time_updated INTEGER DEFAULT 0,
  data TEXT,
  sequence INTEGER
);
"""


def temp_root():
    return tempfile.TemporaryDirectory(prefix="kk-zcode-title-test-")


def make_db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def add_session(conn, session_id, title="新会话", directory="", parent_id=None,
                title_source="first_input", archived=None, updated=1):
    conn.execute(
        "INSERT INTO session (id, slug, directory, title, time_created, time_updated, "
        "time_archived, title_source, parent_id) VALUES (?,?,?,?,1,?,?,?,?)",
        (session_id, session_id, directory, title, updated, archived, title_source, parent_id),
    )


def add_message(conn, session_id, message_id, sequence, data, text=None):
    conn.execute(
        "INSERT INTO message (id, session_id, data, sequence) VALUES (?,?,?,?)",
        (message_id, session_id, json.dumps(data, ensure_ascii=False), sequence),
    )
    if text:
        conn.execute(
            "INSERT INTO part (id, message_id, session_id, data, sequence) VALUES (?,?,?,?,0)",
            (message_id + "-p", message_id, session_id,
             json.dumps({"type": "text", "text": text, "time": {"end": 1}}, ensure_ascii=False)),
        )


class FakeBackend:
    def __init__(self, sessions):
        self.sessions = {item["id"]: dict(item) for item in sessions}

    def read(self, session_id):
        if session_id not in self.sessions:
            from zcode_adapter import BackendError
            raise BackendError("会话不存在：" + session_id)
        return dict(self.sessions[session_id])

    def is_archived(self, session_id):
        return bool(self.sessions[session_id].get("archived"))

    def rename(self, session_id, title):
        self.sessions[session_id]["name"] = title
        self.sessions[session_id]["title_source"] = "generated"

    def list_sessions(self, *, archived=False):
        rows = []
        for item in self.sessions.values():
            is_arch = bool(item.get("archived"))
            if is_arch != archived:
                continue
            rows.append({
                "id": item["id"], "name": item.get("name") or "",
                "cwd": item.get("cwd") or "", "parent_id": item.get("parent_id") or "",
                "title_source": item.get("title_source") or "",
                "time_updated": item.get("time_updated") or 0,
            })
        rows.sort(key=lambda row: row["time_updated"], reverse=True)
        return rows


def user_turn(turn_id, text, assistant=None, finish="stop"):
    items = [{"type": "userMessage", "content": [{"type": "text", "text": text}]}]
    if assistant:
        items.append({"type": "agentMessage", "text": assistant, "phase": "final_answer"})
    return {"id": str(turn_id), "items": items}


class TitleTestCase(unittest.TestCase):
    config = {
        "enabled": True, "recent_turns": 5, "max_context_chars": 8000,
        "model_timeout_seconds": 10, "max_parallel_workers": 1,
    }
