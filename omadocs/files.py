"""Strict local inputs and bounded OOXML inspection, without extraction."""
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET
from .errors import Fault
from .paths import private_file

# Extensible registry: OpenDocument formats are intentionally not enabled.
FORMATS = {
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
}
MAX_XML = 1024 * 1024
MAX_ENTRIES = 100000


def parse_path(value, cwd=None):
    if not isinstance(value, str) or not value or len(value) > 16384 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Fault("invalid_input")
    if value.startswith("file:"):
        if not value.startswith("file://") or re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise Fault("invalid_input")
        uri = urllib.parse.urlsplit(value)
        if uri.scheme != "file" or uri.netloc not in ("", "localhost") or uri.query or uri.fragment or "?" in value or "#" in value:
            raise Fault("invalid_input")
        try:
            value = urllib.parse.unquote(uri.path, encoding="utf-8", errors="strict")
        except UnicodeError:
            raise Fault("invalid_input") from None
        if not value.startswith("/") or value.startswith("//"):
            raise Fault("invalid_input")
    elif re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
        raise Fault("invalid_input")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Fault("invalid_input")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        raise Fault("invalid_input") from None
    p = Path(value)
    if len(p.name.encode("utf-8")) > 255:
        raise Fault("invalid_input")
    return p if p.is_absolute() else Path(cwd or os.getcwd()) / p


def open_regular(path):
    # Walk components by descriptor, refusing symlinks (including parents).
    p = Path(os.path.abspath(path))
    dirfd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in p.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
            os.close(dirfd)
            dirfd = nxt
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise Fault("local_file")
        return fd
    except (OSError, ValueError):
        raise Fault("local_file") from None
    finally:
        os.close(dirfd)


def validate_ooxml(stream, suffix):
    if suffix.lower() not in FORMATS:
        raise Fault("local_file")
    mime, main, content_type = FORMATS[suffix.lower()]
    try:
        # Bound central directory allocation before ZipFile parses entries.
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
        pos = tail.rfind(b"PK\x05\x06")
        if pos < 0 or len(tail) - pos < 22:
            raise Fault("local_file")
        _, disk, cd_disk, disk_entries, entries, cd_size, cd_offset, comment = struct.unpack_from("<4s4H2LH", tail, pos)
        if disk or cd_disk or disk_entries != entries or pos + 22 + comment != len(tail):
            raise Fault("local_file")
        if entries == 65535 or cd_size == 0xffffffff or cd_offset == 0xffffffff:
            eocd_offset = size - len(tail) + pos
            if eocd_offset < 20:
                raise Fault("local_file")
            stream.seek(eocd_offset - 20)
            locator = stream.read(20)
            signature, z_disk, z_offset, disks = struct.unpack("<4sLQL", locator)
            if signature != b"PK\x06\x07" or z_disk or disks != 1 or z_offset >= eocd_offset - 20:
                raise Fault("local_file")
            stream.seek(z_offset)
            record = stream.read(56)
            signature, record_size, made, needed, disk, cd_disk, disk_entries, entries, cd_size, cd_offset = struct.unpack("<4sQHHIIQQQQ", record)
            if signature != b"PK\x06\x06" or not 44 <= record_size <= 1024 or disk or cd_disk or disk_entries != entries or z_offset + record_size + 12 > eocd_offset - 20:
                raise Fault("local_file")
        if entries > MAX_ENTRIES or cd_size > 32 * MAX_XML or cd_offset + cd_size > size:
            raise Fault("local_file")
        stream.seek(0)
        with zipfile.ZipFile(stream) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(infos) > MAX_ENTRIES or len(names) != len(set(names)) or main not in names:
                raise Fault("local_file")
            for item in infos:
                if item.flag_bits & 1 or item.filename.startswith("/") or ".." in item.filename.split("/") or "\\" in item.filename:
                    raise Fault("local_file")
            info = z.getinfo("[Content_Types].xml")
            if info.file_size > MAX_XML or info.compress_size > MAX_XML:
                raise Fault("local_file")
            with z.open(info) as meta:
                xml = meta.read(MAX_XML + 1)
            if len(xml) > MAX_XML or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                raise Fault("local_file")
            tree = ET.fromstring(xml)
            if not any(e.attrib.get("PartName") == "/" + main and e.attrib.get("ContentType") == content_type for e in tree):
                raise Fault("local_file")
        return mime
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile, ET.ParseError, NotImplementedError, struct.error):
        raise Fault("local_file") from None
    finally:
        stream.seek(0)


def fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def snapshot(source, destination):
    srcfd = open_regular(source)
    outfd = None
    try:
        before = os.fstat(srcfd)
        outfd = private_file(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL)
        try:
            fcntl.ioctl(outfd, 0x40049409, srcfd)  # Linux FICLONE
        except OSError as exc:
            if exc.errno not in (errno.EOPNOTSUPP, errno.EXDEV, errno.EINVAL, errno.ENOTTY):
                raise
            while chunk := os.read(srcfd, 1024 * 1024):
                view = memoryview(chunk)
                while view:
                    written = os.write(outfd, view)
                    view = view[written:]
        if fingerprint(before) != fingerprint(os.fstat(srcfd)):
            raise Fault("source_changed")
        os.fsync(outfd)
        os.lseek(outfd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(outfd), "rb") as stream:
            mime = validate_ooxml(stream, Path(source).suffix)
            digest = hashlib.md5(usedforsecurity=False)
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        dirfd = os.open(Path(destination).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        return {"size": before.st_size, "checksum": digest.hexdigest(), "mime": mime}
    except (OSError, ValueError):
        Path(destination).unlink(missing_ok=True)
        raise Fault("local_file") from None
    except BaseException:
        Path(destination).unlink(missing_ok=True)
        raise
    finally:
        os.close(srcfd)
        if outfd is not None:
            os.close(outfd)
