"""Focused tests for version comparison and GitHub release handling."""

import io
import json
import unittest
from unittest.mock import patch

from services.update import checker


class UpdateCheckerTests(unittest.TestCase):
    """Verify version parsing and update metadata without network access."""

    def test_version_tuple_accepts_optional_patch_and_v_prefix(self):
        self.assertEqual(checker._version_tuple("1.2"), (1, 2, 0))
        self.assertEqual(checker._version_tuple("v1.2.3"), (1, 2, 3))

    @patch("services.update.checker.urlopen")
    def test_check_for_update_returns_release_and_direct_exe_link(self, urlopen):
        payload = {
            "tag_name": "v1.1.0",
            "html_url": "https://github.com/nguyendat030805/Auto_tool_edit/releases/tag/v1.1.0",
            "assets": [{
                "name": "app.exe",
                "browser_download_url": "https://github.com/nguyendat030805/Auto_tool_edit/releases/download/v1.1.0/app.exe",
            }],
        }
        urlopen.return_value = io.BytesIO(json.dumps(payload).encode("utf-8"))

        result = checker.check_for_update()

        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest_version"], "1.1.0")
        self.assertEqual(result["download_url"], payload["assets"][0]["browser_download_url"])

    @patch("services.update.checker.urlopen")
    def test_check_for_update_reports_current_version_when_no_newer_release(self, urlopen):
        payload = {"tag_name": "v1.0.0", "assets": []}
        urlopen.return_value = io.BytesIO(json.dumps(payload).encode("utf-8"))

        result = checker.check_for_update()

        self.assertFalse(result["update_available"])
        self.assertIsNone(result["error"])


if __name__ == "__main__":
    unittest.main()
