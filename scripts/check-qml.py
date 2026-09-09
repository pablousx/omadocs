#!/usr/bin/python
"""Resolve Quickshell's virtual qs import without changing the installed shell."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
lint = shutil.which("qmllint") or "/usr/lib/qt6/bin/qmllint"
with tempfile.TemporaryDirectory(prefix="omadocs-qml-") as tmp:
    Path(tmp, "qs").symlink_to(shell, target_is_directory=True)
    result = subprocess.run([lint, "-I", tmp, *(str(root / p) for p in ("BarWidget.qml", "Panel.qml", "Service.qml", "Bridge.qml"))], capture_output=True, text=True)
    text = result.stdout + result.stderr
    if text.strip():
        print(text)
    failed = result.returncode != 0 or "Warning:" in text or "Error:" in text
    if not failed:
        print("QML validation passed (installed Quattro imports, no warnings).")
    raise SystemExit(1 if failed else 0)
