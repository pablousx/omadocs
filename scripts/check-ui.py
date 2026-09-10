#!/usr/bin/python
"""Test real view/bridge behavior with Qt Controls stand-ins for Quattro.

Quickshell embeds its QML plugins in its executable, so ordinary QtTest cannot
load the native shell theme. Native appearance is checked in the running shell.
No Google services, helper processes, or real user state are used here.
"""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
env = dict(os.environ, QT_QPA_PLATFORMTHEME="", QT_QUICK_CONTROLS_STYLE="Basic")
result = subprocess.run([runner, "-platform", "offscreen", "-import", str(root / "tests/qml/stubs"), "-input", str(root / "tests/qml")], env=env)
raise SystemExit(result.returncode)
