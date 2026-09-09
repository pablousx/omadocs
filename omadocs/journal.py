"""Small durable operation journal; no documents, bearer credentials, or mappings."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from .paths import private_file
from .errors import Fault

DEFAULTS = {"choose_account": False, "recent_limit": 100, "recent_days": 30, "snapshot_days": 7}


class Journal:
    def __init__(self, path):
        fd = private_file(path)
        os.close(fd)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise Fault("internal")
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS accounts(
            id TEXT PRIMARY KEY, identity TEXT NOT NULL, email TEXT NOT NULL, label TEXT NOT NULL,
            client TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, auth TEXT NOT NULL DEFAULT 'ready');
          CREATE UNIQUE INDEX IF NOT EXISTS account_identity ON accounts(identity, client);
          CREATE TABLE IF NOT EXISTS operations(
            id TEXT PRIMARY KEY, batch TEXT NOT NULL, account TEXT, name TEXT NOT NULL,
            state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, owner TEXT,
            mime TEXT, size INTEGER, checksum TEXT, drive_id TEXT, progress INTEGER NOT NULL DEFAULT 0,
            error TEXT, url TEXT, browser TEXT NOT NULL DEFAULT 'pending');
          CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS mime_backup(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, time REAL NOT NULL, code TEXT NOT NULL);
          PRAGMA user_version=1;
        ''')

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def rows(self, query, values=()):
        with self.lock:
            return [dict(row) for row in self.db.execute(query, values).fetchall()]

    def execute(self, query, values=()):
        with self.lock:
            return self.db.execute(query, values)

    def operation(self, key):
        rows = self.rows("SELECT * FROM operations WHERE id=?", (key,))
        if not rows:
            raise Fault("not_found")
        return rows[0]

    def account(self, key):
        rows = self.rows("SELECT * FROM accounts WHERE id=?", (key,))
        if not rows:
            raise Fault("not_found")
        return rows[0]

    def update(self, key, **fields):
        allowed = {"account", "owner", "state", "mime", "size", "checksum", "drive_id", "progress", "error", "url", "browser"}
        if not fields.keys() <= allowed:
            raise Fault("internal")
        fields["updated"] = time.time()
        with self.lock:
            self.db.execute("UPDATE operations SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                            (*fields.values(), key))

    def get(self, key, default=None):
        rows = self.rows("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else DEFAULTS.get(key, default)

    def set(self, key, value):
        self.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def event(self, code):
        from .errors import MESSAGES
        if code not in MESSAGES and code not in ("started", "uploaded", "opened", "stopped"):
            code = "internal"
        with self.transaction():
            self.execute("INSERT INTO events(time,code) VALUES(?,?)", (time.time(), code))
            self.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 200)")

    def close(self):
        with self.lock:
            self.db.close()
