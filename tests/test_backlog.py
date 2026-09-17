from __future__ import annotations

import os
import unittest
from pathlib import Path

from support import FakeBackend, TitleTestCase, temp_root, user_turn
from kk_zcode_title import backlog_candidates, atomic_json


class BacklogTests(TitleTestCase):
    def setUp(self):
        self.tmp = temp_root()
        self.root = Path(self.tmp.name)
        os.environ["KK_ZCODE_TITLE_DATA"] = str(self.root)

    def tearDown(self):
        os.environ.pop("KK_ZCODE_TITLE_DATA", None)
        self.tmp.cleanup()

    def test_skips_compliant_custom_subagent_greeting(self):
        sessions = [
            {"id": "sess_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
             "name": "🔧 插件｜安装", "cwd": "demo", "title_source": "generated",
             "parent_id": "", "time_updated": 9, "turns": []},
            {"id": "sess_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
             "name": "改UI", "cwd": "demo", "title_source": "custom",
             "parent_id": "", "time_updated": 8, "turns": []},
            {"id": "sess_cccccccc-cccc-4ccc-8ccc-cccccccccccc",
             "name": "子代理任务", "cwd": "demo", "title_source": "first_input",
             "parent_id": "sess_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
             "time_updated": 7, "turns": []},
            {"id": "sess_dddddddd-dddd-4ddd-8ddd-dddddddddddd",
             "name": "你好", "cwd": "demo", "title_source": "first_input",
             "parent_id": "", "time_updated": 6, "turns": []},
            {"id": "sess_eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
             "name": "帮我看看这个报错", "cwd": "demo", "title_source": "first_input",
             "parent_id": "", "time_updated": 5,
             "turns": [user_turn("1", "帮我看看这个报错", "栈如下")]},
            {"id": "sess_ffffffff-ffff-4fff-8fff-ffffffffffff",
             "name": "当前会话原文", "cwd": "demo", "title_source": "first_input",
             "parent_id": "", "time_updated": 4, "turns": []},
        ]
        locked = "sess_99999999-9999-4999-8999-999999999999"
        sessions.append({
            "id": locked, "name": "锁定的明文标题", "cwd": "demo",
            "title_source": "generated", "parent_id": "", "time_updated": 3, "turns": [],
        })
        atomic_json(self.root / "threads" / (locked + ".json"), {"locked": True})
        backend = FakeBackend(sessions)
        report = backlog_candidates(
            backend, self.root,
            current_id="sess_ffffffff-ffff-4fff-8fff-ffffffffffff",
            limit=20,
        )
        ids = [item["id"] for item in report["candidates"]]
        self.assertEqual(ids, ["sess_eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"])
        self.assertEqual(report["skipped"]["already_formatted"], 1)
        self.assertEqual(report["skipped"]["custom"], 1)
        self.assertEqual(report["skipped"]["subagent"], 1)
        self.assertEqual(report["skipped"]["trivial"], 1)
        self.assertEqual(report["skipped"]["current"], 1)
        self.assertEqual(report["skipped"]["locked"], 1)


if __name__ == "__main__":
    unittest.main()
