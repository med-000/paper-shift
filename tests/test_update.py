"""An updater must verify the release before replacing an installed CLI."""

import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from src import update


class UpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.target = self.home / ".local/bin/pshift"
        self.target.parent.mkdir(parents=True)
        self.target.write_text("old executable")
        self.target.chmod(0o755)
        payload = b"#!/bin/sh\nprintf 'pshift 0.3.1\\n'\n"
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo("pshift")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        self.archive = stream.getvalue()
        self.asset = {
            "name": "pshift-macos-arm64.tar.gz",
            "browser_download_url": "https://github.com/med-000/paper-shift/releases/download/v0.3.1/pshift-macos-arm64.tar.gz",
            "digest": "sha256:" + hashlib.sha256(self.archive).hexdigest(),
        }
        self.patches = [
            patch.object(update.sys, "frozen", True, create=True),
            patch.object(update.sys, "executable", str(self.target)),
            patch("src.update.Path.home", return_value=self.home),
            patch("src.update.version", return_value="0.3.0"),
            patch("src.update.platform.system", return_value="Darwin"),
            patch("src.update.platform.machine", return_value="arm64"),
            patch("src.update._release", return_value={"tag_name": "v0.3.1", "assets": [self.asset]}),
            patch("src.update._request", side_effect=lambda _: io.BytesIO(self.archive)),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_check_only_and_verified_update(self) -> None:
        self.assertEqual(update.update(check=True), "更新可能: 0.3.0 → 0.3.1")
        self.assertEqual(self.target.read_text(), "old executable")
        self.assertEqual(update.update(), "更新しました: 0.3.0 → 0.3.1")
        self.assertIn("pshift 0.3.1", self.target.read_text())

    def test_invalid_digest_never_replaces_executable(self) -> None:
        self.asset["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(update.UpdateError, "チェックサム"):
            update.update()
        self.assertEqual(self.target.read_text(), "old executable")

    def test_wrong_executable_version_never_replaces_executable(self) -> None:
        with patch("src.update.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "pshift 0.3.2\n"
            with self.assertRaisesRegex(update.UpdateError, "バージョン"):
                update.update()
        self.assertEqual(self.target.read_text(), "old executable")

    def test_current_version_does_not_download(self) -> None:
        with patch("src.update._release", return_value={"tag_name": "v0.3.0", "assets": []}):
            self.assertEqual(update.update(), "最新版です: 0.3.0")
        self.assertEqual(self.target.read_text(), "old executable")

    def test_source_installation_does_not_touch_release(self) -> None:
        with patch.object(update.sys, "frozen", False):
            with self.assertRaisesRegex(update.UpdateError, "ソース版"):
                update.update()
        self.assertEqual(self.target.read_text(), "old executable")


if __name__ == "__main__":
    unittest.main()
