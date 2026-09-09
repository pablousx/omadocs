"""Exercise actual xdg-mime with isolated desktop entries and XDG directories."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from omadocs.desktop import Mime, MIMES, DESKTOP_ID
from omadocs.journal import Journal
from omadocs.paths import Paths


class XdgIntegrationTest(unittest.TestCase):
    def test_actual_xdg_default_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="omadocs-xdg-") as tmp:
            root = Path(tmp)
            paths = Paths(*(root / k for k in ("state", "cache", "runtime", "config", "data", "bin")))
            paths.prepare()
            (paths.data / "applications").mkdir(parents=True)
            paths.config.mkdir()
            empty = root / "empty"
            empty.mkdir()
            for index, mime in enumerate(MIMES):
                (paths.data / "applications" / f"previous-{index}.desktop").write_text("[Desktop Entry]\nType=Application\nName=Previous\nExec=/usr/bin/true %U\nMimeType=" + mime + ";\n")
            (paths.config / "mimeapps.list").write_text("[Default Applications]\n" + "".join(mime + f"=previous-{i}.desktop;\n" for i, mime in enumerate(MIMES)))
            env = {"XDG_CURRENT_DESKTOP": "Hyprland", "XDG_CONFIG_HOME": str(paths.config), "XDG_DATA_HOME": str(paths.data), "XDG_CONFIG_DIRS": str(empty), "XDG_DATA_DIRS": str(empty)}
            with patch.dict(os.environ, env):
                journal = Journal(paths.state / "journal.sqlite3")
                try:
                    mime = Mime(paths, journal)
                    before = [mime.query_fn(m) for m in MIMES]
                    self.assertEqual(before, [f"previous-{i}.desktop" for i in range(3)])
                    try:
                        mime.install()
                        self.assertEqual([mime.query_fn(m) for m in MIMES], [DESKTOP_ID] * 3)
                    finally:
                        mime.remove()
                    self.assertEqual([mime.query_fn(m) for m in MIMES], before)
                finally:
                    journal.close()
