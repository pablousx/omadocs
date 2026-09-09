"""Account identities in the journal; OAuth material in the keyring only."""
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid
from .errors import Fault
from .google import CLIENT_RE, Drive, OAuth, read_desktop_credentials


def label_text(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Fault("invalid_input")
    return value.strip()


class Accounts:
    def __init__(self, journal, keyring, oauth=None, drive_factory=None):
        self.journal, self.keyring = journal, keyring
        self.oauth = oauth or OAuth()
        self.drive_factory = drive_factory or (lambda token: Drive(token))
        self.locks = {}
        self.lock = threading.RLock()

    def lock_for(self, key):
        with self.lock:
            return self.locks.setdefault(key, threading.RLock())

    def import_client(self, path):
        client = read_desktop_credentials(path)
        key = hashlib.sha256(client["client_id"].encode()).hexdigest()[:32]
        self.keyring.put("client/" + key, client)
        self.journal.set("active_client", key)
        return {"imported": True, "client": key}

    def current_client(self):
        key = self.journal.get("active_client")
        if key:
            return key, self.client(key)
        p = Path(__file__).resolve().parent.parent / "assets/oauth-client.json"
        try:
            value = json.loads(p.read_text())
            client_id = value.get("client_id")
        except (OSError, ValueError, AttributeError):
            client_id = None
        if not isinstance(client_id, str) or not CLIENT_RE.fullmatch(client_id):
            raise Fault("credentials_required")
        key = hashlib.sha256(client_id.encode()).hexdigest()[:32]
        client = {"client_id": client_id}
        self.keyring.put("client/" + key, client)
        return key, client

    def client(self, key):
        value = self.keyring.get("client/" + key)
        if not isinstance(value, dict) or not CLIENT_RE.fullmatch(value.get("client_id", "")):
            raise Fault("credentials_required")
        return value

    def authorize(self, account_id=None, label=None):
        if label is not None:
            label = label_text(label)
        if account_id:
            old = self.journal.account(account_id)
            key, client = old["client"], self.client(old["client"])
        else:
            if len(self.journal.rows("SELECT id FROM accounts")) >= 64:
                raise Fault("busy")
            old = None
            key, client = self.current_client()
        tokens = self.oauth.authorize(client)
        identity = self.drive_factory(lambda **_: tokens["access_token"]).identity()
        if old and identity["permissionId"] != old["identity"]:
            raise Fault("account_mismatch")
        existing = self.journal.rows("SELECT * FROM accounts WHERE identity=? AND client=?", (identity["permissionId"], key))
        account_id = account_id or (existing[0]["id"] if existing else str(uuid.uuid4()))
        with self.lock_for(account_id):
            self.keyring.put("account/" + account_id, tokens)
            chosen_label = label or (old or (existing[0] if existing else {})).get("label") or identity["emailAddress"]
            # Google values are displayed as plain text; still bound their size.
            chosen_label = str(chosen_label)[:80]
            with self.journal.transaction():
                self.journal.execute("""INSERT INTO accounts(id,identity,email,label,client) VALUES(?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET email=excluded.email,label=excluded.label,auth='ready'""",
                    (account_id, identity["permissionId"], identity["emailAddress"], chosen_label, key))
                if not self.journal.get("default_account") and self.journal.account(account_id)["enabled"]:
                    self.journal.set("default_account", account_id)
        return account_id

    def token(self, key, *, force=False):
        with self.lock_for(key):
            account = self.journal.account(key)
            if not account["enabled"]:
                raise Fault("account_disabled")
            try:
                value = self.keyring.get("account/" + key)
                if not isinstance(value, dict):
                    raise Fault("authentication")
                if force or value.get("expires_at", 0) <= time.time() + 60:
                    value = self.oauth.refresh(self.client(account["client"]), value)
                    self.keyring.put("account/" + key, value)
                self.journal.execute("UPDATE accounts SET auth='ready' WHERE id=?", (key,))
                return value["access_token"]
            except Fault as exc:
                if exc.code in ("authentication", "keyring"):
                    self.journal.execute("UPDATE accounts SET auth=? WHERE id=?", (exc.code, key))
                raise

    def drive(self, key):
        return self.drive_factory(lambda **kwargs: self.token(key, **kwargs))
