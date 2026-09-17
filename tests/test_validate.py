from __future__ import annotations

import unittest

from support import TitleTestCase
from kk_zcode_title import (coerce_legacy_category_emoji, title_compliant,
                            title_has_allowed_emoji, validate_candidate)


class ValidateTests(TitleTestCase):
    def test_accepts_gear_with_and_without_variation_selector(self):
        with_vs = "⚙️ 插件｜安装启用"
        without = "⚙ 插件｜安装启用"
        self.assertTrue(title_has_allowed_emoji(with_vs))
        self.assertTrue(title_has_allowed_emoji(without))
        self.assertTrue(title_compliant(with_vs))
        self.assertTrue(title_compliant(without))

    def test_legacy_puzzle_emoji_is_coerced_without_second_model(self):
        raw = validate_candidate(
            {"action": "rename", "title": "🧩 clip-helper｜字幕裁剪修复", "reason": "开发"},
            "旧标题",
        )
        self.assertEqual(raw["title"], "🔧 clip-helper｜字幕裁剪修复")
        self.assertEqual(coerce_legacy_category_emoji("🛠 邮箱注册｜修复"), "🔧 邮箱注册｜修复")

    def test_rejects_missing_separator(self):
        with self.assertRaises(ValueError):
            validate_candidate(
                {"action": "rename", "title": "🔧 只有对象没有目标", "reason": "x"},
                "旧",
            )


if __name__ == "__main__":
    unittest.main()
