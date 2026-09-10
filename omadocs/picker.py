"""Isolate the desktop file chooser from Quickshell and the upload daemon."""
import os
import secrets
import signal
import subprocess
from .errors import Fault
from .files import parse_path

MAX_OUTPUT = 1024 * 1024


def decode_selection(output, separator, kind):
    if len(output) > MAX_OUTPUT:
        raise Fault("invalid_input")
    try:
        value = output.decode("utf-8", "strict").removesuffix("\n")
    except UnicodeError:
        raise Fault("invalid_input") from None
    if not value:
        return {"cancelled": True}
    values = value.split(separator)
    if not 1 <= len(values) <= (1 if kind == "credentials" else 64):
        raise Fault("invalid_input")
    paths = [parse_path(value) for value in values]
    if any(not value.startswith("/") for value in values):
        raise Fault("invalid_input")
    return {"files": [path.as_uri() for path in paths]}


def pick(kind):
    if kind not in ("files", "credentials"):
        raise Fault("invalid_input")
    # An unpredictable separator preserves spaces and literal punctuation in
    # multiple selections; control characters are rejected by parse_path.
    separator = "__omadocs_" + secrets.token_hex(32) + "__"
    command = ["zenity", "--file-selection", "--separator=" + separator,
               "--title=" + ("Choose Google Desktop OAuth JSON" if kind == "credentials" else "Upload new Office copies to Google Drive")]
    if kind == "files":
        command += ["--multiple", "--file-filter=Office documents | *.docx *.xlsx *.pptx *.DOCX *.XLSX *.PPTX"]
    else:
        command += ["--file-filter=Google credentials | *.json"]
    try:
        process = subprocess.Popen([*command], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   # Keep local-file picking independent of a
                                   # stalled portal or remote-volume service.
                                   env=dict(os.environ, GIO_USE_VFS="local", GDK_DEBUG="no-portals"))
    except OSError:
        return {"error": {"message": "The file picker is unavailable. Install zenity, or use your file manager’s Open with → omadocs action."}}
    def stop(_signum, _frame):
        process.terminate()
        raise SystemExit(0)
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        output = process.stdout.read(MAX_OUTPUT + 1)
        if len(output) > MAX_OUTPUT:
            raise Fault("invalid_input")
        code = process.wait()
        if code == 1:
            return {"cancelled": True}
        if code != 0:
            return {"error": {"message": "The file picker could not finish. Try again, or open the file with omadocs from your file manager."}}
        return decode_selection(output, separator, kind)
    finally:
        signal.signal(signal.SIGTERM, previous)
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
