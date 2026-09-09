import os
from pathlib import Path
import socket
import tempfile
import unittest
import urllib.parse
import zipfile
from unittest.mock import patch
from omadocs.files import parse_path, snapshot, validate_ooxml, FORMATS
from omadocs.errors import Fault
from tests.fakes import office


class PathsTest(unittest.TestCase):
    def test_unicode_and_spaces_paths_and_uris(self):
        value = "/tmp/Informe de México 日本.docx"
        self.assertEqual(str(parse_path(value)), value)
        self.assertEqual(str(parse_path(Path(value).as_uri())), value)
        self.assertEqual(str(parse_path("file://localhost" + urllib.parse.quote(value))), value)
        self.assertEqual(str(parse_path("notes.docx", "/tmp")), "/tmp/notes.docx")

    def test_reject_unsafe_uris(self):
        for value in ("", "https://host/a.docx", "file:/a.docx", "file://evil/a.docx", "file:///a%ZZ.docx", "file:///a%00.docx",
                      "file:///a%0A.docx", "file:///a.docx?", "file:///a.docx#", "file:///a.docx?x=1", "file:///a.docx#tag",
                      "file://user@localhost/a.docx", "file://localhost:80/a.docx", "file:///[bad%ff].docx", "a\x00.docx", "file:////host/a.docx", "/tmp/" + "x" * 256):
            with self.subTest(value=value), self.assertRaises(Fault):
                parse_path(value)

    def test_literal_percent_and_metacharacters_paths(self):
        self.assertEqual(str(parse_path('/tmp/a % $(touch x) `cmd` "quote".docx')), '/tmp/a % $(touch x) `cmd` "quote".docx')


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_formats_and_source_unchanged(self):
        for ext, (mime, _, _) in FORMATS.items():
            source = office(self.root / ("test" + ext))
            original = source.read_bytes()
            mtime = source.stat().st_mtime_ns
            destination = self.root / ("snapshot" + ext)
            result = snapshot(source, destination)
            self.assertEqual(result["mime"], mime)
            self.assertEqual(result["size"], len(original))
            self.assertEqual(destination.read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(source.stat().st_mtime_ns, mtime)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_directory_symlink_device_and_socket(self):
        source = office(self.root / "ok.docx")
        link = self.root / "link.docx"
        link.symlink_to(source)
        fifo = self.root / "fifo.docx"
        os.mkfifo(fifo)
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(self.root / "socket.docx"))
        try:
            for value in (self.root, link, fifo, self.root / "socket.docx", Path("/dev/null")):
                with self.subTest(value=value), self.assertRaises(Fault):
                    snapshot(value, self.root / "out")
                self.assertFalse((self.root / "out").exists())
        finally:
            sock.close()

    def test_parent_symlink_rejected(self):
        office(self.root / "ok.docx")
        link = self.root / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(Fault):
            snapshot(link / "ok.docx", self.root / "out")

    def test_mismatched_extension_and_fake_zip(self):
        source = office(self.root / "wrong.xlsx", suffix=".docx")
        with self.assertRaises(Fault):
            snapshot(source, self.root / "out")
        source.write_bytes(b"PK invalid package")
        with self.assertRaises(Fault):
            snapshot(source, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_hostile_xml_and_zip_metadata(self):
        for xml in (b'<!DOCTYPE a [<!ENTITY x "b">]><Types/>', b'x' * (1024 * 1024 + 1)):
            p = self.root / "bad.docx"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("word/document.xml", "<x/>")
                z.writestr("[Content_Types].xml", xml)
            with self.assertRaises(Fault):
                snapshot(p, self.root / "out")

    def test_copy_failure_cleanup(self):
        source = office(self.root / "ok.docx")
        with patch("omadocs.files.fcntl.ioctl", side_effect=OSError(28, "no space")), self.assertRaises(Fault):
            snapshot(source, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_changed_source_cleanup(self):
        source = office(self.root / "ok.docx")
        from omadocs.files import fingerprint
        with patch("omadocs.files.fingerprint", side_effect=[(1,), (2,)]), self.assertRaises(Fault) as caught:
            snapshot(source, self.root / "out")
        self.assertEqual(caught.exception.code, "source_changed")
        self.assertFalse((self.root / "out").exists())

    def test_streaming_fallback(self):
        source = office(self.root / "ok.docx", size=3 * 1024 * 1024)
        with patch("omadocs.files.fcntl.ioctl", side_effect=OSError(95, "not supported")):
            snapshot(source, self.root / "out")
        self.assertEqual(source.read_bytes(), (self.root / "out").read_bytes())

    def test_zip64_metadata_supported_with_bounded_directory(self):
        source = self.root / "zip64.docx"
        with patch("zipfile.ZIP64_LIMIT", 100):
            office(source, size=512)
        snapshot(source, self.root / "out")
        self.assertEqual(source.read_bytes(), (self.root / "out").read_bytes())
