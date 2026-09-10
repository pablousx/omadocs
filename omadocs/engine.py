"""Upload state machine. Google resources are reachable only through owned jobs."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import threading
import time
import uuid
from . import VERSION
from .accounts import Accounts, label_text, bundled_client_available
from .errors import Fault, MESSAGES
from .files import parse_path, snapshot, open_regular
from .google import backoff, open_browser, summon_panel, validate_url
from .journal import DEFAULTS

TERMINAL = {"complete", "cancelled", "expired"}
CHUNK = 8 * 1024 * 1024
PUBLIC_FIELDS = ("id", "batch", "account", "name", "state", "created", "updated", "owner", "size", "progress", "error", "browser")


class Engine:
    def __init__(self, paths, journal, keyring, *, accounts=None, browser=open_browser, summon=summon_panel, sleep=time.sleep, autostart=True):
        self.paths, self.journal, self.keyring = paths, journal, keyring
        self.accounts = accounts or Accounts(journal, keyring)
        self.browser, self.summon, self.sleep = browser, summon, sleep
        self.lock = threading.RLock()
        self.admission_lock = threading.Lock()
        self.jobs = {}
        self.cancelled = set()
        self.paused = set()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="upload")
        self.auth_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oauth")
        self.auth_state = {"busy": False, "error": None}
        self.auth_target = None
        self.changed = threading.Condition()
        self.generation = 0
        self.stopping = False
        self.autostart = autostart
        self.recover()

    def notify(self):
        with self.changed:
            self.generation += 1
            self.changed.notify_all()

    def snap(self, key):
        # Keys are UUIDs from the journal, never caller-controlled paths.
        try:
            if str(uuid.UUID(key)) != key:
                raise ValueError
        except (ValueError, TypeError):
            raise Fault("invalid_input") from None
        return self.paths.cache / "snapshots" / key

    def recover(self):
        self.journal.execute("UPDATE operations SET state='failed',error='local_file' WHERE state='preparing'")
        self.journal.execute("UPDATE operations SET state='ready' WHERE state='uploading'")
        self.journal.execute("UPDATE operations SET browser='uncertain' WHERE state='complete' AND browser IN ('pending','launching')")
        self.maintenance()
        if self.autostart:
            for op in self.journal.rows("SELECT id FROM operations WHERE state='ready'"):
                self.schedule(op["id"])

    def maintenance(self):
        now = time.time()
        known = {row["id"]: row for row in self.journal.rows("SELECT * FROM operations")}
        for path in (self.paths.cache / "snapshots").iterdir():
            row = known.get(path.name)
            if not row or row["state"] in TERMINAL or row["state"] == "failed" and not row["drive_id"] and row["error"] in ("local_file", "source_changed"):
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
        for key, op in known.items():
            if op["state"] not in TERMINAL and op["state"] != "uploading" and now - op["created"] > self.journal.get("snapshot_days") * 86400:
                self.snap(key).unlink(missing_ok=True)
                if op["state"] != "unresolved":
                    self.journal.update(key, state="unresolved" if op["drive_id"] else "expired", error="snapshot_missing")
            if op["state"] in TERMINAL:
                try:
                    self.keyring.delete("session/" + key)
                except Fault:
                    # Keep row so secret cleanup can be retried next start.
                    continue
                if now - op["updated"] > self.journal.get("recent_days") * 86400:
                    self.journal.execute("DELETE FROM operations WHERE id=?", (key,))
        rows = self.journal.rows("SELECT id,updated FROM operations WHERE state IN ('complete','cancelled','expired') ORDER BY updated DESC")
        for row in rows[self.journal.get("recent_limit"):]:
            # Retain short-lived receipts past the bounded transport retry window.
            if row["updated"] > now - 600:
                continue
            try:
                self.keyring.delete("session/" + row["id"])
                self.journal.execute("DELETE FROM operations WHERE id=?", (row["id"],))
            except Fault:
                pass

    def open(self, files, request_id, account=None, choose=False):
        results = []
        choose = choose or self.journal.get("choose_account") and account is None
        account = account or (None if choose else self.journal.get("default_account"))
        selected = self.journal.account(account) if account else None
        with self.admission_lock:
            selected = self.journal.account(account) if account else None
            state = "waiting_account" if not account else "ready" if selected["enabled"] else "paused"
            if len(self.journal.rows("SELECT id FROM operations WHERE state NOT IN ('complete','cancelled','expired')")) + len(files) > 1000:
                raise Fault("busy")
            for index, source in enumerate(files):
                key = str(uuid.uuid5(uuid.UUID(request_id), str(index)))
                try:
                    existing = self.journal.operation(key)
                except Fault:
                    existing = None
                if existing:
                    results.append({"id": key, "state": existing["state"]})
                    continue
                path = parse_path(source)
                now = time.time()
                self.journal.execute("""INSERT INTO operations(id,batch,account,name,state,created,updated,owner)
                                        VALUES(?,?,?,?,'preparing',?,?,?)""",
                                     (key, request_id, account, path.name, now, now, selected["email"] if selected else None))
                try:
                    meta = snapshot(path, self.snap(key))
                    self.journal.update(key, **meta, state=state, error="account_disabled" if state == "paused" else None)
                    results.append({"id": key, "state": state})
                    if state == "ready" and self.autostart:
                        self.schedule(key)
                except Fault as exc:
                    self.journal.update(key, state="failed", error=exc.code)
                    self.journal.event(exc.code)
                    results.append({"id": key, "state": "failed", "error": exc.public()})
        self.notify()
        if not account or state == "paused":
            self.summon()
        return {"operations": results}

    def schedule(self, key):
        with self.lock:
            if self.stopping or key in self.jobs:
                return
            self.cancelled.discard(key)
            future = self.pool.submit(self.run, key)
            self.jobs[key] = future
            def done(_):
                with self.lock:
                    self.jobs.pop(key, None)
                self.notify()
            future.add_done_callback(done)

    def check(self, key):
        if key in self.cancelled or self.stopping:
            raise Fault("cancelled")
        op = self.journal.operation(key)
        if op["account"] in self.paused:
            raise Fault("account_disabled")
        account = self.journal.account(op["account"])
        if not account["enabled"]:
            raise Fault("account_disabled")
        return op

    def verify(self, op, metadata):
        if not isinstance(metadata, dict):
            raise Fault("invalid_response")
        owner = self.journal.account(op["account"])
        try:
            matches = (metadata.get("id") == op["drive_id"] and metadata.get("mimeType") == op["mime"] and
                       int(metadata.get("size", -1)) == op["size"] and metadata.get("md5Checksum") == op["checksum"] and
                       metadata.get("appProperties", {}).get("omadocsOperation") == op["id"] and
                       metadata.get("ownedByMe") is True and
                       any(item.get("permissionId") == owner["identity"] for item in metadata.get("owners", [])))
        except (ValueError, TypeError, AttributeError):
            matches = False
        if not matches:
            raise Fault("invalid_response")
        return validate_url(metadata.get("webViewLink"), expected_id=op["drive_id"])

    def complete(self, op, drive):
        # A metadata GET is limited to this operation's pre-generated ID.
        url = self.verify(op, drive.metadata(op))
        self.journal.update(op["id"], state="complete", progress=op["size"], error=None, url=url, browser="pending")
        self.journal.event("uploaded")
        self.snap(op["id"]).unlink(missing_ok=True)
        try:
            self.keyring.delete("session/" + op["id"])
        except Fault as exc:
            self.journal.event(exc.code)
        self.notify()
        if op["id"] in self.cancelled:
            self.journal.update(op["id"], browser="skipped")
            self.notify()
        else:
            self.reopen(op["id"])

    def reopen(self, key):
        with self.lock:
            op = self.journal.operation(key)
            if op["state"] != "complete":
                raise Fault("invalid_input")
            if op["browser"] == "launching":
                raise Fault("busy")
            url = validate_url(op["url"], expected_id=op["drive_id"])
            self.journal.update(key, browser="launching")
        try:
            self.browser(url)
            self.journal.update(key, browser="opened")
            self.journal.event("opened")
        except Exception:
            self.journal.update(key, browser="failed")
            self.journal.event("browser")
        self.notify()
        return {"browser": self.journal.operation(key)["browser"]}

    def run(self, key):
        try:
            op = self.check(key)
            if op["state"] in TERMINAL:
                return
            drive = self.accounts.drive(op["account"])
            self.journal.update(key, state="uploading", error=None)
            self.notify()
            # Reconcile completion before requiring local bytes: a successful
            # remote upload may outlive its snapshot or the final response.
            if op["drive_id"]:
                meta = drive.metadata(op)
                if meta is not None:
                    self.complete(op, drive)
                    return
            if not self.snap(key).exists():
                raise Fault("snapshot_missing")
            fd = open_regular(self.snap(key))
            with os.fdopen(fd, "rb") as stream:
                # Cache storage is private but may have been damaged since restart.
                digest = hashlib.md5(usedforsecurity=False)
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                if stream.tell() != op["size"] or digest.hexdigest() != op["checksum"]:
                    raise Fault("snapshot_missing")
                if not op["drive_id"]:
                    self.journal.update(key, drive_id=drive.generate_id())
                    op = self.journal.operation(key)
                session = self.keyring.get("session/" + key)
                restarts = 0
                failures = 0
                while True:
                    self.check(key)
                    if not session:
                        session = drive.initiate(op)
                        if session is None:
                            self.complete(op, drive)
                            return
                        # Store before sending any document bytes.
                        self.keyring.put("session/" + key, session)
                    status = drive.progress(session, op["size"])
                    if status.get("complete"):
                        self.complete(op, drive)
                        return
                    if status.get("expired"):
                        if drive.metadata(op) is not None:
                            self.complete(op, drive)
                            return
                        restarts += 1
                        if restarts > 2:
                            raise Fault("offline")
                        self.keyring.delete("session/" + key)
                        session = None
                        continue
                    offset = status["offset"]
                    if not 0 <= offset < op["size"]:
                        raise Fault("invalid_response")
                    try:
                        while offset < op["size"]:
                            self.check(key)
                            stream.seek(offset)
                            data = stream.read(min(CHUNK, op["size"] - offset))
                            if not data:
                                raise Fault("snapshot_missing")
                            status = drive.chunk(session, offset, data, op["size"], op["mime"])
                            if status.get("complete"):
                                self.complete(op, drive)
                                return
                            if status.get("expired"):
                                break
                            new_offset = status["offset"]
                            if not offset < new_offset <= offset + len(data):
                                raise Fault("invalid_response")
                            offset = new_offset
                            self.journal.update(key, progress=offset)
                            self.notify()
                        # Completion may have arrived without its final metadata.
                    except Fault as exc:
                        if not exc.retryable or failures >= 5:
                            raise
                        failures += 1
                        backoff(failures - 1, exc, self.sleep)
                        # Always probe committed offset before resending bytes.
        except Fault as exc:
            self.fail(key, exc)
        except Exception:
            self.fail(key, Fault("internal"))

    def fail(self, key, exc):
        op = self.journal.operation(key)
        if op["state"] == "complete":
            self.journal.event(exc.code)
            return
        state = {"authentication": "auth_required", "keyring": "auth_required", "account_disabled": "paused",
                 "cancelled": "cancelled", "snapshot_missing": "expired"}.get(exc.code, "failed")
        if exc.code == "snapshot_missing" and op["drive_id"]:
            state = "unresolved"
        if exc.code in ("authentication", "keyring") and op["account"]:
            self.journal.execute("UPDATE accounts SET auth=? WHERE id=?", (exc.code, op["account"]))
        # Shutdown interruption remains recoverable; explicit cancellation does not.
        if self.stopping and key not in self.cancelled:
            state = "ready"
        self.journal.update(key, state=state, error=exc.code)
        if state in TERMINAL:
            self.snap(key).unlink(missing_ok=True)
            try:
                self.keyring.delete("session/" + key)
            except Fault:
                pass
        self.journal.event(exc.code)
        self.notify()

    def retry(self, key):
        op = self.journal.operation(key)
        if op["state"] == "complete":
            return self.reopen(key)
        if op["state"] in TERMINAL or op["state"] in ("preparing", "uploading", "waiting_account"):
            raise Fault("invalid_input")
        self.check(key)
        self.journal.update(key, state="ready", error=None)
        self.schedule(key)
        return {"id": key}

    def cancel(self, key):
        op = self.journal.operation(key)
        if op["state"] == "complete":
            raise Fault("invalid_input")
        with self.lock:
            self.cancelled.add(key)
            if key not in self.jobs:
                self.fail(key, Fault("cancelled"))
        return {"id": key}

    def assign(self, key, account):
        selected = self.journal.account(account)
        if not selected["enabled"]:
            raise Fault("account_disabled")
        op = self.journal.operation(key)
        if op["state"] != "waiting_account" or op["drive_id"]:
            raise Fault("invalid_input")
        # One choice applies to the original invocation's waiting batch.
        waiting = self.journal.rows("SELECT id FROM operations WHERE batch=? AND state='waiting_account'", (op["batch"],))
        with self.journal.transaction():
            for row in waiting:
                self.journal.update(row["id"], account=account, owner=selected["email"], state="ready", error=None)
        for row in waiting:
            self.schedule(row["id"])
        return {"ids": [row["id"] for row in waiting]}

    def authenticate(self, account=None, label=None):
        if label is not None:
            label_text(label)
        with self.lock:
            if self.auth_state["busy"]:
                raise Fault("busy")
            if account:
                self.journal.account(account)
            self.auth_state = {"busy": True, "error": None}
            self.auth_target = account
        def work():
            error = None
            try:
                key = self.accounts.authorize(account, label)
                for op in self.journal.rows("SELECT id FROM operations WHERE account=? AND state='auth_required'", (key,)):
                    self.retry(op["id"])
            except Fault as exc:
                error = exc.code
                self.journal.event(error)
            except Exception:
                error = "internal"
                self.journal.event(error)
            with self.lock:
                self.auth_state = {"busy": False, "error": error}
                self.auth_target = None
            self.notify()
        self.auth_pool.submit(work)
        self.notify()
        return {"started": True}

    def account_action(self, action, key, label=None):
        account = self.journal.account(key)
        if action == "remove":
            # Cancellation interrupts at the next request/chunk boundary. Never
            # remove credentials while a worker still needs to reconcile a PUT.
            if not self.admission_lock.acquire(blocking=False):
                raise Fault("busy")
            try:
                with self.lock:
                    if self.auth_state["busy"] and self.auth_target == key:
                        raise Fault("busy")
                    self.journal.execute("UPDATE accounts SET enabled=0 WHERE id=?", (key,))
                    active_ids = {row["id"] for row in self.journal.rows("SELECT id FROM operations WHERE account=?", (key,))}
                    futures = [future for job, future in self.jobs.items() if job in active_ids]
                    self.cancelled.update(active_ids)
            finally:
                self.admission_lock.release()
            deadline = time.monotonic() + 65
            for future in futures:
                try:
                    future.result(timeout=max(0, deadline - time.monotonic()))
                except TimeoutError:
                    raise Fault("busy") from None
        with self.lock:
            if self.auth_state["busy"] and self.auth_target == key:
                raise Fault("busy")
            if action == "rename":
                self.journal.execute("UPDATE accounts SET label=? WHERE id=?", (label_text(label), key))
            elif action == "set-default":
                if not account["enabled"]:
                    raise Fault("account_disabled")
                self.journal.set("default_account", key)
            elif action in ("disable", "enable"):
                enabled = action == "enable"
                if enabled:
                    self.paused.discard(key)
                else:
                    self.paused.add(key)
                self.journal.execute("UPDATE accounts SET enabled=? WHERE id=?", (int(enabled), key))
                if enabled:
                    for op in self.journal.rows("SELECT id FROM operations WHERE account=? AND state='paused'", (key,)):
                        self.retry(op["id"])
            elif action == "remove":
                active = [row["id"] for row in self.journal.rows("SELECT id FROM operations WHERE account=?", (key,))]
                if any(job in self.jobs and not self.jobs[job].done() for job in active):
                    raise Fault("busy")
                for op in self.journal.rows("SELECT * FROM operations WHERE account=?", (key,)):
                    if op["state"] not in TERMINAL:
                        self.cancel(op["id"])
                    self.keyring.delete("session/" + op["id"])
                self.keyring.delete("account/" + key)
                self.journal.execute("DELETE FROM accounts WHERE id=?", (key,))
                if self.journal.get("default_account") == key:
                    self.journal.set("default_account", None)
            else:
                raise Fault("invalid_input")
        self.notify()
        return {"changed": True}

    def settings(self, key=None, value=None):
        if key is not None:
            if key not in DEFAULTS:
                raise Fault("invalid_input")
            if key == "choose_account":
                if type(value) is not bool:
                    raise Fault("invalid_input")
            else:
                limits = {"recent_limit": (1, 1000), "recent_days": (1, 365), "snapshot_days": (1, 7)}
                if type(value) is not int or not limits[key][0] <= value <= limits[key][1]:
                    raise Fault("invalid_input")
            self.journal.set(key, value)
            self.notify()
        return {k: self.journal.get(k) for k in DEFAULTS}

    def status(self):
        accounts = self.journal.rows("SELECT id,email,label,enabled,auth FROM accounts ORDER BY label")
        rows = self.journal.rows("SELECT * FROM operations WHERE state NOT IN ('complete','cancelled','expired') ORDER BY created DESC")
        rows += self.journal.rows("SELECT * FROM operations WHERE state IN ('complete','cancelled','expired') ORDER BY updated DESC LIMIT ?", (self.journal.get("recent_limit"),))
        operations = [{k: row[k] for k in PUBLIC_FIELDS} for row in rows]
        return {"version": VERSION, "accounts": accounts, "default_account": self.journal.get("default_account"),
                "operations": operations, "authentication": dict(self.auth_state), "settings": self.settings(),
                "setup": {"client_configured": bool(self.journal.get("active_client")) or bundled_client_available()},
                "active": sum(row["state"] in ("preparing", "ready", "uploading") for row in rows),
                "attention": sum(row["state"] in ("failed", "auth_required", "waiting_account", "paused", "unresolved") or row["browser"] in ("failed", "uncertain") for row in rows)}

    def diagnostics(self):
        import importlib.util
        import shutil
        states = self.journal.rows("SELECT state,COUNT(*) AS count FROM operations GROUP BY state")
        return {"version": VERSION, "journal_version": 1,
                "dependencies": {name: importlib.util.find_spec(name) is not None for name in ("requests", "secretstorage")},
                "desktop_tools": {name: shutil.which(name) is not None for name in ("xdg-open", "xdg-mime", "omarchy-shell")},
                "accounts": len(self.journal.rows("SELECT id FROM accounts")),
                "states": {row["state"]: row["count"] for row in states},
                "events": self.journal.rows("SELECT time,code FROM events ORDER BY id DESC LIMIT 100"),
                "authentication": dict(self.auth_state), "production_client": bundled_client_available()}

    def shutdown(self):
        self.stopping = True
        self.pool.shutdown(wait=True, cancel_futures=False)
        self.auth_pool.shutdown(wait=True, cancel_futures=False)
        self.journal.event("stopped")
