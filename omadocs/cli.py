"""Documented CLI and private Quickshell bridge entry points."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from . import VERSION, PLUGIN_ID
from .errors import Fault, MESSAGES
from .files import parse_path
from .ipc import call, envelope


def parser():
    p = argparse.ArgumentParser(prog="omadocs", description="Upload a NEW Office copy to Google Drive; local files never synchronize.")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)
    opening = sub.add_parser("open", help="Upload each file as a new Drive copy")
    group = opening.add_mutually_exclusive_group()
    group.add_argument("--account", metavar="ID")
    group.add_argument("--choose-account", action="store_true")
    opening.add_argument("--wait", action="store_true", help="Wait until this batch completes or needs attention")
    opening.add_argument("files", nargs="+")
    accounts = sub.add_parser("accounts").add_subparsers(dest="action", required=True)
    accounts.add_parser("list")
    add = accounts.add_parser("add")
    add.add_argument("--label")
    for verb in ("rename", "reauthenticate", "enable", "disable", "remove", "set-default"):
        a = accounts.add_parser(verb)
        a.add_argument("id")
        if verb == "rename":
            a.add_argument("label")
    creds = sub.add_parser("credentials").add_subparsers(dest="action", required=True)
    creds.add_parser("import").add_argument("path")
    sub.add_parser("status").add_argument("--json", action="store_true")
    activity = sub.add_parser("activity").add_subparsers(dest="action", required=True)
    for verb in ("retry", "cancel", "reopen", "assign"):
        a = activity.add_parser(verb)
        a.add_argument("id")
        if verb == "assign":
            a.add_argument("account")
    mime = sub.add_parser("mime").add_subparsers(dest="action", required=True)
    for verb in ("status", "install", "remove"):
        mime.add_parser(verb)
    settings = sub.add_parser("settings").add_subparsers(dest="action", required=True)
    settings.add_parser("get")
    setter = settings.add_parser("set")
    setter.add_argument("key", choices=("choose_account", "recent_limit", "recent_days", "snapshot_days"))
    setter.add_argument("value", help="JSON boolean or integer")
    sub.add_parser("diagnostics").add_argument("--json", action="store_true")
    bundle = sub.add_parser("support-bundle")
    bundle.add_argument("--output", required=True)
    sub.add_parser("uninstall", help="Disable the plugin, restore MIME defaults, and erase local omadocs credentials/history")
    return p


def support_bundle(path, diagnostics):
    # Construct from an allowlisted diagnostics object, not filesystem archives.
    allowed = {"version", "journal_version", "dependencies", "desktop_tools", "accounts", "states", "events", "authentication", "production_client"}
    if not isinstance(diagnostics, dict) or not diagnostics.keys() <= allowed:
        raise Fault("internal")
    content = json.dumps(diagnostics, indent=2, sort_keys=True).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                info = tarfile.TarInfo("diagnostics.json")
                info.size = len(content)
                info.mode = 0o600
                info.mtime = 0
                archive.addfile(info, io.BytesIO(content))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def execute(args):
    command = args.command
    if command == "open":
        params = {"files": [str(parse_path(value)) for value in args.files]}
        if args.account:
            params["account"] = args.account
        if args.choose_account:
            params["choose"] = True
        result = call(envelope("open", params))
        if args.wait:
            ids = {row["id"] for row in result["operations"]}
            while True:
                status = call(envelope("status"))
                rows = [row for row in status["operations"] if row["id"] in ids]
                if all(row["state"] not in ("preparing", "ready", "uploading") and row["browser"] != "launching" for row in rows):
                    return {"operations": rows}
                time.sleep(0.5)
        return result
    if command == "accounts":
        if args.action == "list":
            status = call(envelope("status"))
            return {"accounts": status["accounts"], "default_account": status["default_account"]}
        params = {k: getattr(args, k) for k in ("id", "label") if getattr(args, k, None) is not None}
        return call(envelope("accounts." + args.action, params))
    if command == "credentials":
        return call(envelope("credentials.import", {"path": str(parse_path(args.path))}))
    if command == "activity":
        params = {"id": args.id}
        if args.action == "assign":
            params["account"] = args.account
        return call(envelope("activity." + args.action, params))
    if command == "mime":
        return call(envelope("mime." + args.action))
    if command == "settings":
        params = {}
        if args.action == "set":
            try:
                params = {"key": args.key, "value": json.loads(args.value)}
            except ValueError:
                raise Fault("invalid_input") from None
        return call(envelope("settings." + args.action, params))
    if command == "support-bundle":
        support_bundle(parse_path(args.output), call(envelope("diagnostics")))
        return {"created": True, "redacted": True}
    if command == "uninstall":
        # The shell wrapper sends IPC to the existing process; it never starts one.
        try:
            subprocess.run(["omarchy-shell", "shell", "setPluginEnabled", PLUGIN_ID, "false"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return call(envelope("uninstall"))
    return call(envelope(command))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv == ["_serve"]:
            from .ipc import serve
            return serve()
        if argv == ["_bridge"]:
            from .ipc import bridge, harden
            harden()
            return bridge()
        if len(argv) == 2 and argv[0] == "_pick":
            from .ipc import harden
            from .picker import pick
            harden()
            try:
                result = pick(argv[1])
            except Fault as exc:
                result = {"error": exc.public()}
            print(json.dumps(result, ensure_ascii=True))
            return 0
        args = parser().parse_args(argv)
        result = execute(args)
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        if args.command == "open" and any(row.get("state") in ("failed", "expired", "cancelled", "auth_required", "paused", "unresolved") for row in result["operations"]):
            return 1
        return 0
    except Fault as exc:
        print(json.dumps({"error": exc.public()}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError):
        print(json.dumps({"error": Fault("local_file").public()}), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({"error": Fault("internal").public()}), file=sys.stderr)
        return 1
