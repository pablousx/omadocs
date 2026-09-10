"""Versioned, bounded local RPC. Never carries tokens or OAuth callbacks."""
import fcntl
import json
import os
import resource
from pathlib import Path
import socket
import socketserver
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid
from .errors import Fault
from .paths import Paths, private_file

MAX_MESSAGE = 1024 * 1024
MAX_REPLY = 4 * MAX_MESSAGE
PROTOCOL = 1
SCHEMAS = {
    "hello": ({}, {}), "shutdown": ({}, {}),
    "status": ({}, {}), "subscribe": ({}, {}), "diagnostics": ({}, {}),
    "open": ({"files": list}, {"account": str, "choose": bool}),
    "accounts.add": ({}, {"label": str}),
    "accounts.reauthenticate": ({"id": str}, {}),
    "accounts.rename": ({"id": str, "label": str}, {}),
    "accounts.enable": ({"id": str}, {}), "accounts.disable": ({"id": str}, {}),
    "accounts.remove": ({"id": str}, {}), "accounts.set-default": ({"id": str}, {}),
    "credentials.import": ({"path": str}, {}),
    "activity.retry": ({"id": str}, {}), "activity.cancel": ({"id": str}, {}),
    "activity.reopen": ({"id": str}, {}), "activity.assign": ({"id": str, "account": str}, {}),
    "mime.status": ({}, {}), "mime.install": ({}, {}), "mime.remove": ({}, {}),
    "settings.get": ({}, {}), "settings.set": ({"key": str, "value": (bool, int)}, {}),
    "uninstall": ({}, {}),
}


def uuid_text(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise Fault("ipc") from None
    return value


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def decode(data, *, limit=MAX_MESSAGE):
    if not data or len(data) > limit:
        raise Fault("ipc")
    try:
        return json.loads(data, object_pairs_hook=reject_duplicates, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise Fault("ipc") from None


def validate(message):
    if not isinstance(message, dict) or set(message) != {"version", "id", "method", "params"} or type(message["version"]) is not int or message["version"] != PROTOCOL:
        raise Fault("ipc")
    uuid_text(message["id"])
    method, params = message["method"], message["params"]
    if not isinstance(method, str) or method not in SCHEMAS or not isinstance(params, dict):
        raise Fault("ipc")
    required, optional = SCHEMAS[method]
    if not required.keys() <= params.keys() or not params.keys() <= required.keys() | optional.keys():
        raise Fault("ipc")
    for key, value in params.items():
        types = (required | optional)[key]
        if type(value) not in (types if isinstance(types, tuple) else (types,)):
            raise Fault("ipc")
        if isinstance(value, str) and (not value or len(value) > 16384 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise Fault("ipc")
    for key in ("id", "account"):
        if key in params:
            uuid_text(params[key])
    if method == "open":
        from .files import parse_path
        files = params["files"]
        if not 1 <= len(files) <= 64:
            raise Fault("ipc")
        for value in files:
            if not isinstance(value, str) or not parse_path(value).is_absolute() or not (value.startswith("/") or value.startswith("file://")):
                raise Fault("ipc")
    if method == "credentials.import" and not Path(params["path"]).is_absolute():
        raise Fault("ipc")
    return message


def envelope(method, params=None, request_id=None):
    return {"version": PROTOCOL, "id": request_id or str(uuid.uuid4()), "method": method, "params": params or {}}


def encode(data):
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def socket_connect(paths):
    sock = None
    try:
        st = paths.socket.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise Fault("ipc")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(90)
        sock.connect(str(paths.socket))
        _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        if uid != os.getuid():
            sock.close()
            raise Fault("ipc")
        return sock
    except OSError:
        if sock is not None:
            sock.close()
        raise Fault("ipc") from None


def ensure_helper(paths):
    paths.prepare()
    lockfd = private_file(paths.runtime / "start.lock")
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        try:
            with socket_connect(paths) as sock:
                hello = envelope("hello")
                sock.sendall(encode(hello))
                with sock.makefile("rb") as reader:
                    reply = decode(reader.readline(MAX_MESSAGE + 1))
            from . import build_id
            if reply.get("result", {}).get("build") == build_id():
                return
            # Protocol-compatible older helpers are stopped only while idle.
            # Running uploads keep their existing code until completion.
            call(envelope("shutdown"), paths, start=False)
            for _ in range(100):
                if not paths.socket.exists():
                    break
                time.sleep(0.1)
            else:
                raise Fault("busy")
        except Fault:
            if paths.socket.exists():
                # A stale socket from a killed process is safe to replace only
                # when no live peer answers it.
                try:
                    sock = socket_connect(paths)
                    sock.close()
                except Fault:
                    pass
                else:
                    raise
        launcher = Path(__file__).resolve().parent.parent / "omadocs-run"
        subprocess.Popen([sys.executable, "-I", str(launcher), "_serve"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
        for _ in range(100):
            time.sleep(0.1)
            try:
                sock = socket_connect(paths)
                sock.close()
                return
            except Fault:
                pass
        raise Fault("ipc")
    finally:
        os.close(lockfd)


def call(message, paths=None, *, start=True):
    validate(message)
    paths = paths or Paths.user()
    if start:
        ensure_helper(paths)
    for attempt in range(2):
        try:
            with socket_connect(paths) as sock:
                sock.sendall(encode(message))
                with sock.makefile("rb") as reader:
                    raw = reader.readline(MAX_REPLY + 1)
                    result = decode(raw, limit=MAX_REPLY)
            if not isinstance(result, dict) or result.get("id") != message["id"] or result.get("version") != PROTOCOL:
                raise Fault("ipc")
            if "error" in result:
                raise Fault(result["error"].get("code", "ipc"))
            return result["result"]
        except Fault as exc:
            if exc.code != "ipc" or attempt == 1:
                raise
            if start:
                ensure_helper(paths)
        except (OSError, KeyError, TypeError):
            if attempt == 1:
                raise Fault("ipc") from None
            # Reuse the request ID so a lost open acknowledgment is harmless.
    raise Fault("ipc")


class Dispatcher:
    def __init__(self, engine, mime):
        self.engine, self.mime = engine, mime
        from . import build_id
        self.build = build_id()

    def dispatch(self, message):
        validate(message)
        method, params = message["method"], message["params"]
        e = self.engine
        if method == "hello":
            return {"build": self.build, "version": PROTOCOL}
        if method == "shutdown":
            with e.lock:
                if e.jobs or e.auth_state["busy"] or e.admission_lock.locked():
                    raise Fault("busy")
                e.stopping = True
                e.notify()
            return {"stopping": True}
        if method == "status":
            return e.status()
        if method == "diagnostics":
            return e.diagnostics()
        if method == "open":
            return e.open(params["files"], message["id"], params.get("account"), params.get("choose", False))
        if method == "accounts.add":
            return e.authenticate(label=params.get("label"))
        if method == "accounts.reauthenticate":
            return e.authenticate(account=params["id"])
        if method.startswith("accounts."):
            return e.account_action(method.split(".")[1], params["id"], params.get("label"))
        if method == "credentials.import":
            return e.accounts.import_client(params["path"])
        if method.startswith("activity."):
            action = method.split(".")[1]
            if action == "assign":
                return e.assign(params["id"], params["account"])
            return getattr(e, {"retry": "retry", "cancel": "cancel", "reopen": "reopen"}[action])(params["id"])
        if method.startswith("mime."):
            result = getattr(self.mime, method.split(".")[1])()
            e.notify()
            return result
        if method == "settings.get":
            return e.settings()
        if method == "settings.set":
            return e.settings(params["key"], params["value"])
        if method == "uninstall":
            with e.lock:
                if e.auth_state["busy"] or e.jobs:
                    raise Fault("busy")
                self.mime.remove()
                # Deletion is restricted by the Secret Service application tag.
                e.keyring.delete_all()
                for op in e.journal.rows("SELECT id FROM operations"):
                    e.snap(op["id"]).unlink(missing_ok=True)
                with e.journal.transaction():
                    for table in ("accounts", "operations", "settings", "events"):
                        e.journal.execute("DELETE FROM " + table)
                e.notify()
                return {"uninstalled": True}
        raise Fault("ipc")


def harden():
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    import ctypes
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE
        raise Fault("internal")
    # Libraries must never write request URLs, bodies, or exception reprs.
    import logging
    logging.disable(logging.CRITICAL)
    sys.excepthook = lambda *_: sys.stderr.write("omadocs: internal error\n")
    threading.excepthook = lambda _: None


def serve(paths=None, *, components=None):
    harden()
    from .journal import Journal
    from .secrets import Keyring
    from .engine import Engine
    from .desktop import Mime
    paths = paths or Paths.user()
    paths.prepare()
    lockfd = private_file(paths.runtime / "daemon.lock")
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lockfd)
        return 0
    if paths.socket.exists() or paths.socket.is_symlink():
        st = paths.socket.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid():
            raise Fault("ipc")
        paths.socket.unlink()
    if components is None:
        journal = Journal(paths.state / "journal.sqlite3")
        engine = Engine(paths, journal, Keyring())
        mime = Mime(paths, journal)
        try:
            mime.refresh_generated()
        except (Fault, OSError):
            # A desktop repair failure must not prevent accounts/activity from
            # loading. Keep backups so explicit MIME setup can retry later.
            journal.event("mime")
    else:
        # Python dependency injection for integration tests. No production CLI,
        # QML request, or environment variable can select an alternate backend.
        journal, engine, mime = components(paths)
    dispatcher = Dispatcher(engine, mime)
    journal.event("started")

    class Handler(socketserver.StreamRequestHandler):
        def setup(self):
            self.server.last_request = time.monotonic()
            super().setup()

        def finish(self):
            try:
                super().finish()
            finally:
                self.server.last_request = time.monotonic()

        def handle(self):
            request_id = None
            try:
                _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
                if uid != os.getuid():
                    return
                self.request.settimeout(90)
                raw = self.rfile.readline(MAX_MESSAGE + 1)
                if not raw:
                    return
                message = validate(decode(raw))
                request_id = message["id"]
                if message["method"] == "subscribe":
                    with self.server.clients_lock:
                        self.server.clients += 1
                    try:
                        while not engine.stopping:
                            with engine.changed:
                                generation = engine.generation
                            self.wfile.write(encode({"version": PROTOCOL, "event": "status", "data": engine.status()}))
                            self.wfile.flush()
                            with engine.changed:
                                engine.changed.wait_for(lambda: engine.generation != generation or engine.stopping, 15)
                    finally:
                        with self.server.clients_lock:
                            self.server.clients -= 1
                    return
                result = dispatcher.dispatch(message)
                response = {"version": PROTOCOL, "id": request_id, "result": result}
            except Fault as exc:
                response = {"version": PROTOCOL, "id": request_id, "error": exc.public()}
            except (OSError, BrokenPipeError):
                return
            except Exception:
                journal.event("internal")
                response = {"version": PROTOCOL, "id": request_id, "error": Fault("internal").public()}
            try:
                self.wfile.write(encode(response))
                self.wfile.flush()
            except OSError:
                pass

    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True
        block_on_close = False
        clients = 0
        clients_lock = threading.Lock()
        slots = threading.BoundedSemaphore(64)
        last_request = time.monotonic()
        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

        def handle_error(self, request, client_address):
            journal.event("ipc")

    try:
        with Server(str(paths.socket), Handler) as server:
            os.chmod(paths.socket, 0o600)
            server.timeout = 1
            idle_since = time.monotonic()
            last_cleanup = idle_since
            while not engine.stopping:
                server.handle_request()
                with engine.lock, server.clients_lock:
                    busy = bool(engine.jobs) or engine.auth_state["busy"] or server.clients > 0 or engine.admission_lock.locked()
                now = time.monotonic()
                if busy:
                    idle_since = now
                if now - last_cleanup >= 60:
                    with engine.admission_lock:
                        engine.maintenance()
                    last_cleanup = now
                if now - max(idle_since, server.last_request) > 60:
                    break
    finally:
        engine.shutdown()
        paths.socket.unlink(missing_ok=True)
        journal.close()
        os.close(lockfd)
    return 0


def bridge(paths=None):
    """One JSON stream for QML; RPC replies and local status events only."""
    paths = paths or Paths.user()
    ensure_helper(paths)
    output_lock = threading.Lock()
    stopped = threading.Event()
    def output(value):
        with output_lock:
            try:
                sys.stdout.buffer.write(encode(value))
                sys.stdout.buffer.flush()
            except (OSError, BrokenPipeError):
                stopped.set()
    def commands():
        while not stopped.is_set():
            line = sys.stdin.buffer.readline(MAX_MESSAGE + 1)
            if not line:
                stopped.set()
                return
            message = None
            try:
                message = validate(decode(line))
                result = call(message, paths)
                output({"version": PROTOCOL, "id": message["id"], "result": result})
            except Fault as exc:
                output({"version": PROTOCOL, "id": message["id"] if message else None, "error": exc.public()})
    threading.Thread(target=commands, daemon=True).start()
    with socket_connect(paths) as sock:
        sock.sendall(encode(envelope("subscribe")))
        sock.settimeout(20)
        with sock.makefile("rb") as reader:
            while not stopped.is_set():
                try:
                    raw = reader.readline(MAX_REPLY + 1)
                    data = decode(raw, limit=MAX_REPLY)
                    if not isinstance(data, dict) or data.get("event") != "status" or data.get("version") != PROTOCOL:
                        raise Fault("ipc")
                    output(data)
                except (OSError, Fault):
                    return 1
    return 0
