import hashlib
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
from omadocs.desktop import Mime, DESKTOP_ID, MIMES, entry, set_entry, desktop_quote, read_text
from omadocs.errors import Fault
from tests.base import EngineCase


class MimeTest(EngineCase):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "Hyprland"})
        self.env.start()
        self.defaults = {mime: f"previous-{i}.desktop" for i, mime in enumerate(MIMES)}
        self.mime = Mime(self.paths, self.journal, root=self.root / "plugin space", query=self.query)
        self.paths.config.mkdir()
        self.original = "# Keep my comments\n[Default Applications]\ntext/plain=editor.desktop;\n" + "".join(mime + "=" + value + ";\n" for mime, value in self.defaults.items()) + "\n[Added Associations]\ntext/plain=another.desktop;\n"
        self.mime.target().write_text(self.original)

    def query(self, mime):
        value = entry(read_text(self.mime.target()), mime)
        return value.split(";")[0] if value else self.defaults.get(mime, "")

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def test_install_restore_exact_existing_text(self):
        self.mime.install()
        self.assertTrue(all(self.query(m) == DESKTOP_ID for m in MIMES))
        self.mime.remove()
        self.assertEqual(self.mime.target().read_text(), self.original)
        self.assertFalse((self.paths.bin / "omadocs").exists())
        self.assertFalse((self.paths.data / "applications" / DESKTOP_ID).exists())

    def test_install_is_repeatable(self):
        self.mime.install()
        self.mime.install()
        self.mime.remove()
        self.assertEqual(self.mime.target().read_text(), self.original)

    def test_runtime_update_refresh_preserves_defaults_and_restoration(self):
        self.mime.install()
        changed = set_entry(self.mime.target().read_text(), MIMES[0], "chosen-later.desktop;")
        self.mime.target().write_text(changed)
        self.mime.root = self.root / "new runtime"
        self.mime.refresh_generated()
        self.assertIn(str(self.mime.root / "omadocs-run"), (self.paths.bin / "omadocs").read_text())
        self.assertEqual(self.mime.target().read_text(), changed)
        self.mime.remove()
        self.assertFalse((self.paths.bin / "omadocs").exists())
        self.assertEqual(self.query(MIMES[0]), "chosen-later.desktop")
        self.assertEqual(self.query(MIMES[1]), self.defaults[MIMES[1]])

    def test_refresh_preserves_modified_and_absent_launchers(self):
        self.mime.refresh_generated()
        self.assertFalse((self.paths.bin / "omadocs").exists())
        self.mime.install()
        (self.paths.bin / "omadocs").write_text("edited launcher")
        self.mime.root = self.root / "new runtime"
        self.mime.refresh_generated()
        self.assertEqual((self.paths.bin / "omadocs").read_text(), "edited launcher")

    def test_launcher_follows_manifest_after_old_runtime_removed(self):
        import json
        import shutil
        root = self.root / 'plugin space $dollar `literal` "quote" %'
        old = root / "runtime" / "old"
        new = root / "runtime" / "new"
        old.mkdir(parents=True)
        new.mkdir()
        (root / ".omadocs-development-source").write_text("test checkout")
        (root / "manifest.json").write_text(json.dumps({"id": DESKTOP_ID.removesuffix(".desktop"), "entryPoints": {"service": "runtime/new/Service.qml"}}))
        (new / "omadocs-run").write_text("import json,sys\nprint(json.dumps(sys.argv[1:]))\n")
        self.mime.root = old
        self.mime.install()
        shutil.rmtree(old)
        source = str(self.root / 'Informe México $(literal) "quote".docx')
        result = subprocess.run(['/usr/bin/python', '-I', str(self.paths.bin / 'omadocs'), 'open', '--', source], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['open', '--', source])

    def test_new_user_default_is_preserved(self):
        self.mime.install()
        changed = set_entry(self.mime.target().read_text(), MIMES[0], "chosen-later.desktop;")
        self.mime.target().write_text(changed)
        self.mime.remove()
        self.assertEqual(self.query(MIMES[0]), "chosen-later.desktop")
        self.assertEqual(self.query(MIMES[1]), self.defaults[MIMES[1]])

    def test_unset_defaults_remove_entries(self):
        self.mime.target().unlink()
        self.defaults = {}
        self.mime.install()
        self.mime.remove()
        self.assertFalse(self.mime.target().exists())
        self.assertEqual(self.query(MIMES[0]), "")

    def test_partial_install_failure_rolls_back(self):
        original = self.mime.query_fn
        def query(mime):
            if mime == MIMES[1] and entry(read_text(self.mime.target()), mime) == DESKTOP_ID + ";":
                return self.defaults[mime]
            return original(mime)
        self.mime.query_fn = query
        with self.assertRaises(Fault):
            self.mime.install()
        self.assertNotEqual(self.query(MIMES[0]), DESKTOP_ID)
        self.assertFalse(self.journal.rows("SELECT key FROM mime_backup"))

    def test_unrelated_launcher_not_overwritten(self):
        self.paths.bin.mkdir()
        (self.paths.bin / "omadocs").write_text("my own tool")
        with self.assertRaises(Fault):
            self.mime.install()
        self.assertEqual((self.paths.bin / "omadocs").read_text(), "my own tool")

    def test_modified_generated_file_not_deleted(self):
        self.mime.install()
        (self.paths.bin / "omadocs").write_text("edited launcher")
        self.mime.remove()
        self.assertEqual((self.paths.bin / "omadocs").read_text(), "edited launcher")

    def test_desktop_entry_validation_and_argument_quoting(self):
        self.mime.install()
        path = self.paths.data / "applications" / DESKTOP_ID
        process = subprocess.run(["desktop-file-validate", str(path)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn(' open -- %U', path.read_text())
        self.assertIn('"', desktop_quote('/a path/a"$`%'))
        self.assertIn('%%', desktop_quote('/a%'))

    def test_duplicate_mime_entries_rejected(self):
        with self.assertRaises(Fault):
            entry("[Default Applications]\na/b=x.desktop;\na/b=y.desktop;\n", "a/b")

    def test_desktop_launch_preserves_literal_arguments(self):
        import importlib.util
        if importlib.util.find_spec("gi") is None:
            self.skipTest("PyGObject is needed for the optional native desktop launcher check")
        import gi
        gi.require_version("GioUnix", "2.0")
        from gi.repository import GioUnix
        import json
        import time
        root = self.root / 'plugin space $dollar `literal` "quote" %'
        root.mkdir()
        received = self.root / "received.json"
        (root / "omadocs-run").write_text("import json,sys\nfrom pathlib import Path\nPath(" + repr(str(received)) + ").write_text(json.dumps(sys.argv[1:]))\n")
        mime = Mime(self.paths, self.journal, root=root, query=self.query)
        for path, content, mode in mime.generated():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(mode)
        desktop = self.paths.data / "applications" / DESKTOP_ID
        app = GioUnix.DesktopAppInfo.new_from_filename(str(desktop))
        self.assertIsNotNone(app)
        uri = (self.root / 'Informe México $(literal) "quote".docx').as_uri()
        self.assertTrue(app.launch_uris([uri], None))
        for _ in range(100):
            if received.exists():
                break
            time.sleep(.01)
        from omadocs.files import parse_path
        args = json.loads(received.read_text())
        self.assertEqual(args[:2], ["open", "--"])
        self.assertEqual(parse_path(args[2]), parse_path(uri))
