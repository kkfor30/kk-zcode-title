from __future__ import annotations

import os
import unittest
from pathlib import Path

from support import add_message, add_session, make_db, temp_root


class ReadTurnsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_root()
        self.db = os.path.join(self.tmp.name, "db.sqlite")
        self.conn = make_db(Path(self.db))
        os.environ["KK_ZCODE_TITLE_DB"] = self.db
        from zcode_adapter import ZCodeBackend
        self.Backend = ZCodeBackend

    def tearDown(self):
        self.conn.close()
        os.environ.pop("KK_ZCODE_TITLE_DB", None)
        self.tmp.cleanup()

    def _turns(self, sid="sess_11111111-1111-4111-8111-111111111111"):
        self.conn.commit()
        with self.Backend() as backend:
            return backend.read(sid)["turns"]

    def test_skips_synthetic_todo_and_keeps_real_user(self):
        sid = "sess_11111111-1111-4111-8111-111111111111"
        add_session(self.conn, sid, title="原标题")
        add_message(self.conn, sid, "u1", 1, {"role": "user"}, "修复邮箱验证码")
        add_message(self.conn, sid, "a1", 2, {"role": "assistant", "finish": "stop"}, "已修复")
        add_message(self.conn, sid, "todo", 3, {
            "role": "user", "synthetic": True, "source": "todo_reminder",
            "visibility": "model-only",
        }, "待办：还要补测试")
        turns = self._turns(sid)
        self.assertEqual(len(turns), 1)
        texts = [p["text"] for p in turns[0]["items"][0]["content"]]
        self.assertEqual(texts, ["修复邮箱验证码"])
        self.assertTrue(any(i["type"] == "agentMessage" for i in turns[0]["items"]))

    def test_skips_agent_runtime_origin(self):
        sid = "sess_11111111-1111-4111-8111-111111111111"
        add_session(self.conn, sid)
        add_message(self.conn, sid, "inj", 1, {
            "role": "user", "semantics": {"origin": "agent_runtime"},
        }, "系统注入")
        add_message(self.conn, sid, "u1", 2, {"role": "user", "semantics": {"origin": "real_user"}},
                    "真实请求")
        add_message(self.conn, sid, "a1", 3, {"role": "assistant", "finish": "completed"}, "好")
        turns = self._turns(sid)
        self.assertEqual(len(turns), 1)
        self.assertIn("真实请求", turns[0]["items"][0]["content"][0]["text"])

    def test_empty_finish_is_not_final_answer(self):
        sid = "sess_11111111-1111-4111-8111-111111111111"
        add_session(self.conn, sid)
        add_message(self.conn, sid, "u1", 1, {"role": "user"}, "还在生成")
        add_message(self.conn, sid, "a1", 2, {"role": "assistant"}, "半段回答")
        turns = self._turns(sid)
        self.assertEqual(len(turns), 1)
        self.assertFalse(any(i["type"] == "agentMessage" for i in turns[0]["items"]))

    def test_completed_finish_counts_as_final_answer(self):
        sid = "sess_11111111-1111-4111-8111-111111111111"
        add_session(self.conn, sid)
        add_message(self.conn, sid, "u1", 1, {"role": "user"}, "部署服务")
        add_message(self.conn, sid, "tool", 2, {"role": "assistant", "finish": "tool-calls"}, "调用工具")
        add_message(self.conn, sid, "a1", 3, {"role": "assistant", "finish": "completed"}, "已上线")
        turns = self._turns(sid)
        agents = [i for i in turns[0]["items"] if i["type"] == "agentMessage"]
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["text"], "已上线")

    def test_todo_does_not_change_content_fingerprint(self):
        sid = "sess_11111111-1111-4111-8111-111111111111"
        add_session(self.conn, sid, title="🐛 邮箱｜修复")
        add_message(self.conn, sid, "u1", 1, {"role": "user"}, "修复邮箱")
        add_message(self.conn, sid, "a1", 2, {"role": "assistant", "finish": "stop"}, "好")
        self.conn.commit()
        from zcode_adapter import ZCodeBackend
        from kk_zcode_title import snapshot
        config = {"recent_turns": 5, "max_context_chars": 8000}
        with ZCodeBackend() as backend:
            first = snapshot(backend.read(sid), config)["fingerprint"]
        add_message(self.conn, sid, "todo", 3, {
            "role": "user", "synthetic": True, "source": "todo_reminder", "visibility": "model-only",
        }, "新待办")
        self.conn.commit()
        with ZCodeBackend() as backend:
            second = snapshot(backend.read(sid), config)["fingerprint"]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
