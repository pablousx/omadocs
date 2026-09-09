#!/usr/bin/python
"""Guarded real-user MIME round trip. Always attempts restoration in finally."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from omadocs.desktop import Mime, MIMES, DESKTOP_ID
from omadocs.journal import Journal
from omadocs.paths import Paths

paths = Paths.user()
paths.prepare()
journal = Journal(paths.state / "journal.sqlite3")
mime = Mime(paths, journal)
try:
    if journal.rows("SELECT key FROM mime_backup"):
        raise SystemExit("Existing MIME setup/backups detected. Restore them before running this validation.")
    before = [mime.query_fn(m) for m in MIMES]
    if DESKTOP_ID in before:
        raise SystemExit("omadocs is already a default. Refusing to replace its original backups.")
    try:
        mime.install()
        actual = [mime.query_fn(m) for m in MIMES]
        if actual != [DESKTOP_ID] * 3:
            raise RuntimeError("Not all MIME defaults changed")
        print("Installed and verified DOCX, XLSX, and PPTX handlers.")
    finally:
        mime.remove()
    after = [mime.query_fn(m) for m in MIMES]
    if after != before:
        raise RuntimeError("MIME defaults differ after restoration; inspect before proceeding.")
    print("Restored and verified:", ", ".join(after))
finally:
    journal.close()
