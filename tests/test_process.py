"""Real process death, durable SQLite, and real Unix socket validation."""
import json
import multiprocessing
from multiprocessing.managers import BaseManager
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from omadocs.accounts import Accounts
from omadocs.engine import Engine
from omadocs.google import Drive
from omadocs.ipc import call, envelope, decode, MAX_MESSAGE, socket_connect
from omadocs.journal import Journal
from omadocs.paths import Paths
from tests.fakes import FakeGoogle, FakeOAuth, MemoryKeyring, CLIENT, office


class FakeManager(BaseManager):
    pass
FakeManager.register("Google", FakeGoogle)
FakeManager.register("Keyring", MemoryKeyring)


def crash_worker(paths, key, account, google, keyring, phase):
    """Injected boundaries live in test code, never in the production helper."""
    from omadocs.engine import CHUNK
    journal = Journal(paths.state / "journal.sqlite3")
    class Wire:
        def request(self, *args, **kwargs):
            response = google.request(*args, **kwargs)
            method, url = args[:2]
            if phase == "id_response" and "/generateIds?" in url:
                os._exit(72)
            if phase == "session_response" and method == "POST" and "/upload/" in url:
                os._exit(72)
            if method == "PUT" and kwargs.get("data"):
                if phase == "chunk_commit" and response.status == 308:
                    os._exit(72)
                if phase == "remote_commit" and response.status in (200, 201):
                    os._exit(72)
            return response
    accounts = Accounts(journal, keyring, FakeOAuth(), lambda token: Drive(token, Wire(), sleep=lambda _: None))
    def browser(_):
        keyring.put("test-browser-count", (keyring.get("test-browser-count") or 0) + 1)
        if phase == "browser_launch":
            os._exit(72)
    engine = Engine(paths, journal, keyring, accounts=accounts, browser=browser, summon=lambda: None, sleep=lambda _: None, autostart=False)
    update = journal.update
    def update_then_crash(job, **fields):
        update(job, **fields)
        if phase == "id_journal" and fields.get("drive_id") or phase == "completion_journal" and fields.get("state") == "complete":
            os._exit(72)
    journal.update = update_then_crash
    engine.run(key)
    engine.shutdown()
    journal.close()


class CrashProcessTest(unittest.TestCase):
    def test_process_death_at_durable_boundaries(self):
        ctx = multiprocessing.get_context("spawn")
        with FakeManager(ctx=ctx) as manager:
            for phase in ("id_response", "id_journal", "session_response", "chunk_commit", "remote_commit", "completion_journal", "browser_launch"):
                with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="omadocs-crash-") as temp:
                    root = Path(temp)
                    paths = Paths(*(root / k for k in ("state", "cache", "runtime", "config", "data", "bin")))
                    paths.prepare()
                    journal = Journal(paths.state / "journal.sqlite3")
                    google, keyring = manager.Google(), manager.Keyring()
                    accounts = Accounts(journal, keyring, FakeOAuth(), lambda token: Drive(token, google, sleep=lambda _: None))
                    keyring.put("client/test-client", {"client_id": CLIENT})
                    journal.set("active_client", "test-client")
                    account = accounts.authorize()
                    engine = Engine(paths, journal, keyring, accounts=accounts, summon=lambda: None, autostart=False)
                    source = office(root / "large.docx", size=8 * 1024 * 1024 + 50)
                    key = engine.open([str(source)], str(uuid.uuid4()))["operations"][0]["id"]
                    engine.shutdown()
                    journal.close()
                    crash = ctx.Process(target=crash_worker, args=(paths, key, account, google, keyring, phase))
                    crash.start(); crash.join(20)
                    if crash.is_alive():
                        crash.kill(); crash.join()
                        self.fail("Crash worker did not reach boundary")
                    self.assertEqual(crash.exitcode, 72)
                    recover = ctx.Process(target=crash_worker, args=(paths, key, account, google, keyring, "recover"))
                    recover.start(); recover.join(20)
                    if recover.is_alive():
                        recover.kill(); recover.join()
                        self.fail("Recovery did not finish")
                    self.assertEqual(recover.exitcode, 0)
                    journal = Journal(paths.state / "journal.sqlite3")
                    op = journal.operation(key)
                    self.assertEqual(op["state"], "complete")
                    self.assertEqual(google.stats()["files"], 1)
                    self.assertFalse((paths.cache / "snapshots" / key).exists())
                    if phase in ("completion_journal", "browser_launch"):
                        self.assertEqual(op["browser"], "uncertain")
                        self.assertEqual(keyring.get("test-browser-count") or 0, int(phase == "browser_launch"))
                    else:
                        self.assertEqual(keyring.get("test-browser-count"), 1)
                    journal.close()


class SocketProcessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omadocs-ipc-")
        root = Path(self.temp.name)
        self.paths = Paths(*(root / k / "omadocs" for k in ("state", "cache", "runtime", "config", "data", "bin")))
        self.paths.prepare()
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ, XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
                   XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_DATA_HOME=str(root / "data"), OMARCHY_PATH="")
        self.process = subprocess.Popen([sys.executable, "-I", str(repo / "omadocs-run"), "_serve"], env=env,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(100):
            if self.paths.socket.exists():
                break
            if self.process.poll() is not None:
                self.fail("Helper exited before socket startup")
            time.sleep(0.02)
        else:
            self.fail("Helper socket did not appear")

    def tearDown(self):
        try:
            call(envelope("shutdown"), self.paths, start=False)
        except Exception:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
        out, err = self.process.communicate(timeout=5)
        self.assertEqual(out, b"")
        self.assertEqual(err, b"")
        self.temp.cleanup()

    def test_real_rpc_and_socket_permissions(self):
        self.assertEqual(self.paths.socket.stat().st_mode & 0o777, 0o600)
        status = call(envelope("status"), self.paths, start=False)
        self.assertEqual(status["accounts"], [])
        result = call(envelope("settings.set", {"key": "choose_account", "value": True}), self.paths, start=False)
        self.assertTrue(result["choose_account"])
        self.assertIn("build", call(envelope("hello"), self.paths, start=False))

    def test_malformed_client_is_rejected_without_stopping_server(self):
        with socket_connect(self.paths) as sock:
            sock.sendall(b'{"version":1,"id":"bad","method":"status","params":{}}\n')
            with sock.makefile("rb") as stream:
                reply = decode(stream.readline(MAX_MESSAGE + 1))
            self.assertEqual(reply["error"]["code"], "ipc")
        self.assertEqual(call(envelope("status"), self.paths, start=False)["active"], 0)

    def test_concurrent_real_client_receipts(self):
        import concurrent.futures
        source = office(Path(self.temp.name) / "document.docx")
        request = envelope("open", {"files": [str(source)]})
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            values = list(pool.map(lambda _: call(request, self.paths, start=False), range(5)))
        self.assertEqual(len({v["operations"][0]["id"] for v in values}), 1)
        status = call(envelope("status"), self.paths, start=False)
        self.assertEqual(len(status["operations"]), 1)
        self.assertEqual(status["operations"][0]["state"], "waiting_account")
