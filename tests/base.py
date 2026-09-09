import os
from pathlib import Path
import tempfile
import unittest
import uuid
from omadocs.accounts import Accounts
from omadocs.engine import Engine
from omadocs.google import Drive
from omadocs.journal import Journal
from omadocs.paths import Paths
from tests.fakes import FakeGoogle, FakeOAuth, MemoryKeyring, CLIENT


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omadocs-test-")
        self.root = Path(self.temp.name)
        self.paths = Paths(*(self.root / name for name in ("state", "cache", "runtime", "config", "data", "bin")))
        self.paths.prepare()
        self.journal = Journal(self.paths.state / "journal.sqlite3")
        self.keyring = MemoryKeyring()
        self.google = FakeGoogle()
        self.oauth = FakeOAuth()
        self.accounts = Accounts(self.journal, self.keyring, self.oauth, lambda token: Drive(token, self.google, sleep=lambda _: None))
        self.keyring.put("client/test-client", {"client_id": CLIENT})
        self.journal.set("active_client", "test-client")
        self.account = self.accounts.authorize(label="Personal")
        self.browser_calls = []
        self.engine = Engine(self.paths, self.journal, self.keyring, accounts=self.accounts,
                             browser=self.browser_calls.append, summon=lambda: None, sleep=lambda _: None, autostart=False)

    def open(self, path, **kwargs):
        result = self.engine.open([str(path)], str(uuid.uuid4()), **kwargs)
        return result["operations"][0]["id"]

    def tearDown(self):
        self.engine.shutdown()
        self.journal.close()
        self.temp.cleanup()
