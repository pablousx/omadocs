import concurrent.futures
import json
import os
import time
import uuid
from unittest.mock import patch
from omadocs.engine import Engine, CHUNK
from omadocs.errors import Fault
from tests.base import EngineCase
from tests.fakes import office


class UploadTest(EngineCase):
    def test_success_unchanged_source_owner_and_browser(self):
        path = office(self.root / "Informe México.docx")
        original = path.read_bytes()
        key = self.open(path)
        self.engine.run(key)
        op = self.journal.operation(key)
        self.assertEqual((op["state"], op["browser"]), ("complete", "opened"))
        self.assertEqual(op["owner"], self.google.email)
        self.assertEqual(len(self.browser_calls), 1)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(self.engine.snap(key).exists())
        self.assertNotIn("session/" + key, self.keyring.values)

    def test_second_open_is_new_but_request_retry_is_same(self):
        path = office(self.root / "same.docx")
        request = str(uuid.uuid4())
        first = self.engine.open([str(path)], request)["operations"][0]["id"]
        self.engine.run(first)
        again = self.engine.open([str(path)], request)["operations"][0]["id"]
        self.assertEqual(first, again)
        second = self.open(path)
        self.engine.run(second)
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.google.files), 2)

    def test_concurrent_opens(self):
        paths = [office(self.root / f"file {i}.docx") for i in range(12)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            keys = list(pool.map(self.open, paths))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(self.engine.run, keys))
        self.assertEqual(len(self.google.files), 12)
        self.assertTrue(all(self.journal.operation(k)["state"] == "complete" for k in keys))

    def test_same_request_concurrent_admission(self):
        path = office(self.root / "file.docx")
        request = str(uuid.uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.engine.open([str(path)], request), range(4)))
        keys = {r["operations"][0]["id"] for r in results}
        self.assertEqual(len(keys), 1)
        self.assertEqual(len(self.journal.rows("SELECT id FROM operations")), 1)

    def test_lost_final_response_reconciles_without_duplicate(self):
        key = self.open(office(self.root / "file.docx"))
        once = [False]
        def lose(call, response):
            if call["method"] == "PUT" and call["data"] and not once[0]:
                once[0] = True
                raise Fault("offline", retryable=True)
        self.google.after = lose
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(len(self.google.files), 1)
        self.assertEqual(self.google.generated, 1)

    def test_chunk_recovery_uses_committed_offset(self):
        key = self.open(office(self.root / "large.docx", size=CHUNK + 500))
        once = [False]
        def lose(call, response):
            if call["method"] == "PUT" and call["data"] and response.status == 308 and not once[0]:
                once[0] = True
                raise Fault("offline", retryable=True)
        self.google.after = lose
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        puts = [c for c in self.google.calls if c["method"] == "PUT" and c["data"]]
        self.assertEqual(len(puts), 2)
        self.assertIn(f"bytes {CHUNK}-", puts[1]["headers"]["Content-Range"])

    def test_expired_session_restarts_same_id(self):
        key = self.open(office(self.root / "file.docx"))
        once = [False]
        def expire(call):
            if call["method"] == "PUT" and not once[0]:
                once[0] = True
                self.google.sessions.clear()
        self.google.before = expire
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(self.google.generated, 1)
        self.assertEqual(len(self.google.files), 1)

    def test_browser_failure_then_reopen_no_upload(self):
        key = self.open(office(self.root / "file.docx"))
        def broken(_):
            raise OSError("injected failure")
        self.engine.browser = broken
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(self.journal.operation(key)["browser"], "failed")
        count = len(self.google.calls)
        self.engine.browser = self.browser_calls.append
        self.engine.retry(key)
        self.assertEqual(len(self.google.calls), count)
        self.assertEqual(self.journal.operation(key)["browser"], "opened")

    def test_invalid_metadata_does_not_open_browser(self):
        for field, value in (("md5Checksum", "wrong"), ("mimeType", "application/vnd.google-apps.document"), ("ownedByMe", False), ("webViewLink", "https://evil.test/file")):
            with self.subTest(field=field):
                self.google.metadata_override = lambda meta: dict(meta, **{field: value})
                key = self.open(office(self.root / "file.docx"))
                self.engine.run(key)
                self.assertEqual(self.journal.operation(key)["error"], "invalid_response")
        self.assertFalse(self.browser_calls)

    def test_crash_after_upload_before_journal_completion(self):
        key = self.open(office(self.root / "file.docx"))
        def crash(call, response):
            if call["method"] == "PUT" and call["data"]:
                raise SystemExit("simulated crash")
        self.google.after = crash
        with self.assertRaises(SystemExit):
            self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "uploading")
        self.google.after = None
        self.engine.recover()
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(len(self.google.files), 1)

    def test_crash_in_browser_launch_requires_explicit_reopen(self):
        key = self.open(office(self.root / "file.docx"))
        self.engine.browser = lambda _: (_ for _ in ()).throw(SystemExit())
        with self.assertRaises(SystemExit):
            self.engine.run(key)
        self.engine.recover()
        self.assertEqual(self.journal.operation(key)["browser"], "uncertain")
        self.assertEqual(len(self.google.files), 1)
        self.assertFalse(self.browser_calls)

    def test_completed_remote_recovered_without_snapshot(self):
        key = self.open(office(self.root / "file.docx"))
        self.engine.run(key)
        self.journal.update(key, state="uploading", browser="pending")
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(len(self.google.files), 1)

    def test_missing_snapshot_never_reopens_source(self):
        key = self.open(office(self.root / "file.docx"))
        self.engine.snap(key).unlink()
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "expired")
        self.assertFalse(self.google.files)

    def test_cancel_and_orphan_cleanup(self):
        key = self.open(office(self.root / "file.docx"))
        self.engine.cancel(key)
        self.assertFalse(self.engine.snap(key).exists())
        orphan = self.paths.cache / "snapshots" / str(uuid.uuid4())
        orphan.write_text("orphan")
        self.engine.maintenance()
        self.assertFalse(orphan.exists())
        self.assertFalse(self.google.files)

    def test_expiry_cleanup(self):
        key = self.open(office(self.root / "file.docx"))
        self.journal.execute("UPDATE operations SET created=? WHERE id=?", (time.time() - 8 * 86400, key))
        self.engine.maintenance()
        self.assertEqual(self.journal.operation(key)["state"], "expired")
        self.assertFalse(self.engine.snap(key).exists())

    def test_default_missing_waits_without_fallback(self):
        self.journal.set("default_account", None)
        key = self.open(office(self.root / "file.docx"))
        self.assertEqual(self.journal.operation(key)["state"], "waiting_account")
        self.assertFalse(self.google.files)

    def test_explicit_account_beats_picker_setting(self):
        self.journal.set("choose_account", True)
        key = self.open(office(self.root / "file.docx"), account=self.account)
        self.assertEqual(self.journal.operation(key)["state"], "ready")

    def test_disabled_default_does_not_fallback(self):
        self.engine.account_action("disable", self.account)
        with self.assertRaises(Fault) as exc:
            self.open(office(self.root / "file.docx"))
        self.assertEqual(exc.exception.code, "account_disabled")

    def test_expired_authentication_pauses(self):
        saved = self.keyring.get("account/" + self.account)
        saved["expires_at"] = 0
        self.keyring.put("account/" + self.account, saved)
        self.oauth.refresh_error = Fault("authentication")
        key = self.open(office(self.root / "file.docx"))
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "auth_required")
        self.assertTrue(self.engine.snap(key).exists())
        self.assertFalse(self.google.files)

    def test_refresh_serialized(self):
        saved = self.keyring.get("account/" + self.account)
        saved["expires_at"] = 0
        self.keyring.put("account/" + self.account, saved)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.accounts.token(self.account), range(8)))
        self.assertEqual(self.oauth.refreshes, 1)

    def test_reauthentication_identity_mismatch(self):
        self.google.identity_id = "different-google-account"
        with self.assertRaises(Fault) as exc:
            self.accounts.authorize(self.account)
        self.assertEqual(exc.exception.code, "account_mismatch")

    def test_account_rename_default_and_remove(self):
        self.engine.account_action("rename", self.account, "Work")
        self.assertEqual(self.journal.account(self.account)["label"], "Work")
        key = self.open(office(self.root / "file.docx"))
        self.engine.account_action("remove", self.account)
        self.assertIsNone(self.journal.get("default_account"))
        self.assertNotIn("account/" + self.account, self.keyring.values)
        self.assertFalse(self.engine.snap(key).exists())
        self.assertFalse(self.google.files)

    def test_keyring_failure_before_upload(self):
        key = self.open(office(self.root / "file.docx"))
        self.keyring.locked = True
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["error"], "keyring")
        self.assertFalse(self.google.files)

    def test_quota_and_permission_are_distinct(self):
        for code in ("quota", "permission", "offline"):
            self.google.before = lambda _: (_ for _ in ()).throw(Fault(code))
            key = self.open(office(self.root / "file.docx"))
            self.engine.run(key)
            self.assertEqual(self.journal.operation(key)["error"], code)

    def test_unresolved_upload_identity_survives_snapshot_expiry(self):
        key = self.open(office(self.root / "unresolved.docx"))
        self.journal.update(key, drive_id=self.accounts.drive(self.account).generate_id())
        self.journal.execute("UPDATE operations SET created=? WHERE id=?", (time.time() - 8 * 86400, key))
        self.engine.maintenance()
        self.assertEqual(self.journal.operation(key)["state"], "unresolved")
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "unresolved")
        self.assertFalse(self.google.files)
        self.engine.cancel(key)
        self.assertEqual(self.journal.operation(key)["state"], "cancelled")

    def test_batch_account_assignment(self):
        self.journal.set("choose_account", True)
        paths = [office(self.root / f"batch {i}.docx") for i in range(3)]
        result = self.engine.open([str(p) for p in paths], str(uuid.uuid4()))
        ids = [r["id"] for r in result["operations"]]
        with patch.object(self.engine, "schedule") as schedule:
            self.engine.assign(ids[0], self.account)
        self.assertEqual(schedule.call_count, 3)
        self.assertTrue(all(self.journal.operation(key)["account"] == self.account for key in ids))

    def test_cancel_after_remote_commit_does_not_open_browser(self):
        key = self.open(office(self.root / "cancelled.docx"))
        def cancel(call, response):
            if call["method"] == "PUT" and call["data"]:
                self.engine.cancelled.add(key)
        self.google.after = cancel
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["state"], "complete")
        self.assertEqual(self.journal.operation(key)["browser"], "skipped")
        self.assertFalse(self.browser_calls)
        self.assertEqual(len(self.google.files), 1)

    def test_view_link_must_name_uploaded_file(self):
        self.google.metadata_override = lambda meta: dict(meta, webViewLink="https://drive.google.com/file/d/some-other-file/view")
        key = self.open(office(self.root / "document.docx"))
        self.engine.run(key)
        self.assertEqual(self.journal.operation(key)["error"], "invalid_response")
        self.assertFalse(self.browser_calls)
