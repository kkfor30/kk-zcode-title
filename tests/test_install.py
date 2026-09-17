from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT


class InstallHookPatchTests(unittest.TestCase):
    def test_patch_writes_current_interpreter(self):
        sys.path.insert(0, str(ROOT))
        import install
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "plugin"
            shutil.copytree(ROOT / "hooks", dest / "hooks")
            command = install.patch_hook_interpreter(dest, python_exe=r"C:\Python\python.exe")
            self.assertEqual(command, r"C:\Python\python.exe")
            data = json.loads((dest / "hooks" / "hooks.json").read_text(encoding="utf-8"))
            hook = data["hooks"]["Stop"][0]["hooks"][0]
            self.assertEqual(hook["command"], r"C:\Python\python.exe")
            self.assertEqual(hook["args"][1], "hook")

    def test_read_json_refuses_to_clobber_corrupt_file(self):
        sys.path.insert(0, str(ROOT))
        import install
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(SystemExit):
                install.read_json(path, {})


if __name__ == "__main__":
    unittest.main()
