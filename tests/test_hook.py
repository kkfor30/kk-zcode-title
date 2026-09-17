from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from support import ROOT, temp_root


SCRIPT = ROOT / "scripts" / "kk_zcode_title.py"


class HookEntryTests(unittest.TestCase):
    def _run(self, payload, extra_env=None, timeout=8):
        tmp = temp_root()
        env = os.environ.copy()
        env["KK_ZCODE_TITLE_DATA"] = tmp.name
        env["KK_ZCODE_TITLE_DB"] = str(Path(tmp.name) / "missing.sqlite")
        env.pop("KK_ZCODE_TITLE_WORKER", None)
        if extra_env:
            env.update(extra_env)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "hook"],
                input=payload, capture_output=True, timeout=timeout,
                env=env, cwd=str(ROOT), text=True, encoding="utf-8",
            )
            return proc, Path(tmp.name)
        finally:
            tmp.cleanup()

    def test_empty_stdin_returns_empty_json(self):
        proc, _ = self._run("")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_camel_case_session_id_returns_empty_json(self):
        payload = json.dumps({
            "hookEventName": "Stop",
            "sessionId": "sess_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        })
        proc, _ = self._run(payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_env_session_id_used_when_json_blank(self):
        payload = json.dumps({"hook_event_name": "Stop", "session_id": ""})
        proc, _ = self._run(payload, extra_env={
            "CLAUDE_SESSION_ID": "sess_cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        })
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_invalid_session_still_returns_empty_json(self):
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "sess_smoke"})
        proc, _ = self._run(payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "{}")


if __name__ == "__main__":
    unittest.main()
