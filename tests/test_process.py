from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import Mock

from support import FakeBackend, TitleTestCase, temp_root, user_turn
from kk_zcode_title import EXCERPT_VERSION, process_thread, snapshot


class ProcessThreadTests(TitleTestCase):
    def setUp(self):
        self.tmp = temp_root()
        self.root = Path(self.tmp.name)
        os.environ["KK_ZCODE_TITLE_DATA"] = str(self.root)

    def tearDown(self):
        os.environ.pop("KK_ZCODE_TITLE_DATA", None)
        self.tmp.cleanup()

    def _thread(self, **kwargs):
        base = {
            "id": "sess_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "name": "🔧 邮箱注册｜过期修复",
            "cwd": "D:/proj/demo",
            "title_source": "generated",
            "parent_id": "",
            "archived": False,
            "turns": [
                user_turn("1", "修复邮箱验证码过期", "已修好"),
            ],
        }
        base.update(kwargs)
        return base

    def test_custom_title_never_calls_model(self):
        thread = self._thread(title_source="custom", name="改UI")
        backend = FakeBackend([thread])
        generator = Mock(side_effect=AssertionError("不应调用模型"))
        result = process_thread(backend, generator, thread["id"], self.root, self.config, apply=True)
        self.assertEqual(result["status"], "manual_title")
        generator.assert_not_called()

    def test_excerpt_version_migrate_skips_model_for_compliant_title(self):
        thread = self._thread()
        backend = FakeBackend([thread])
        state_dir = self.root / "threads"
        state_dir.mkdir()
        from kk_zcode_title import atomic_json, snapshot as snap
        before = snap(thread, self.config)
        atomic_json(state_dir / (thread["id"] + ".json"), {
            "last_fingerprint": "old-scheme",
            "last_generated_title": thread["name"],
            "last_seen_title": thread["name"],
            "excerpt_version": 0,
        })
        generator = Mock(side_effect=AssertionError("升级摘录版本不应打模型"))
        result = process_thread(backend, generator, thread["id"], self.root, self.config, apply=True)
        self.assertEqual(result["status"], "unchanged")
        generator.assert_not_called()
        saved = (state_dir / (thread["id"] + ".json")).read_text(encoding="utf-8")
        self.assertIn(before["fingerprint"], saved)
        self.assertIn(str(EXCERPT_VERSION), saved)

    def test_trivial_latest_turn_keeps_compliant_title_without_model(self):
        thread = self._thread(turns=[
            user_turn("1", "修复邮箱验证码过期", "已修好"),
            user_turn("2", "继续", "好的"),
        ])
        backend = FakeBackend([thread])
        from kk_zcode_title import atomic_json, snapshot as snap
        before = snap(thread, self.config)
        atomic_json(self.root / "threads" / (thread["id"] + ".json"), {
            "last_fingerprint": "different",
            "last_generated_title": thread["name"],
            "last_seen_title": thread["name"],
            "excerpt_version": EXCERPT_VERSION,
        })
        generator = Mock(side_effect=AssertionError("问候续写不应打模型"))
        result = process_thread(backend, generator, thread["id"], self.root, self.config, apply=True)
        self.assertEqual(result["status"], "kept")
        generator.assert_not_called()
        self.assertEqual(result["title"], thread["name"])
        self.assertEqual(before["fingerprint"] != "different", True)

    def test_turn_not_settled_when_last_turn_has_no_assistant(self):
        import kk_zcode_title as mod
        old = mod.SETTLE_TIMEOUT_SECONDS
        mod.SETTLE_TIMEOUT_SECONDS = 0
        try:
            thread = self._thread(turns=[user_turn("1", "还在说", assistant=None)])
            backend = FakeBackend([thread])
            generator = Mock(side_effect=AssertionError("未完成轮次不应打模型"))
            result = mod.process_thread(
                backend, generator, thread["id"], self.root, self.config,
                apply=True, event_turn="latest",
            )
            self.assertEqual(result["status"], "turn_not_settled")
            generator.assert_not_called()
        finally:
            mod.SETTLE_TIMEOUT_SECONDS = old

    def test_rename_apply_uses_generator_once(self):
        thread = self._thread(name="帮我修邮箱验证码")
        backend = FakeBackend([thread])
        generator = Mock(return_value=({"action": "rename", "title": "🐛 邮箱注册｜过期修复",
                                        "reason": "修复故障"}, {"prompt_tokens": 1}))
        result = process_thread(backend, generator, thread["id"], self.root, self.config, apply=True)
        self.assertEqual(result["status"], "renamed")
        self.assertEqual(backend.sessions[thread["id"]]["name"], "🐛 邮箱注册｜过期修复")
        self.assertEqual(generator.call_count, 1)


if __name__ == "__main__":
    unittest.main()
