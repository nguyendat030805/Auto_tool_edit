"""Tests for selecting the video worker entry point."""

import unittest
from unittest.mock import patch

from services.video import web_job


class VideoCommandPrefixTests(unittest.TestCase):
    """Ensure packaged and source runs use the correct CLI entry point."""

    def test_source_run_uses_make_video_script(self):
        with patch.object(web_job.sys, "frozen", False, create=True):
            self.assertEqual(
                web_job._video_command_prefix(),
                [web_job.sys.executable, str(web_job.PROJECT_ROOT / "make_video.py")],
            )

    def test_frozen_run_reenters_executable_in_video_mode(self):
        with (
            patch.object(web_job.sys, "frozen", True, create=True),
            patch.object(web_job.sys, "executable", r"D:\dist\app.exe"),
        ):
            self.assertEqual(
                web_job._video_command_prefix(),
                [r"D:\dist\app.exe", "--video-cli"],
            )


if __name__ == "__main__":
    unittest.main()
