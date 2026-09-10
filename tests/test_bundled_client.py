import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omadocs.accounts import bundled_client
from omadocs.errors import Fault
from tests.base import EngineCase
from tests.fakes import CLIENT, CLIENT_SECRET


class BundleParsingTest(unittest.TestCase):
    def test_only_desktop_application_fields_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "client.json"
            for value in ({"client_id": CLIENT}, {"client_id": CLIENT, "client_secret": CLIENT_SECRET}):
                path.write_text(json.dumps(value))
                self.assertEqual(bundled_client(path), value)
            for value in ({}, [], {"client_id": 1}, {"client_id": "placeholder"},
                          {"client_id": CLIENT, "refresh_token": "not-allowed"},
                          {"client_id": CLIENT, "token_uri": "https://example.test"},
                          {"client_id": CLIENT, "client_secret": ""},
                          {"client_id": CLIENT, "client_secret": "line\nbreak"}):
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(Fault) as error:
                    bundled_client(path)
                self.assertEqual(error.exception.code, "credentials_required")

    def test_missing_oversized_and_malformed_bundles_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(Fault):
                bundled_client(path)
            for raw in (b"{" , b"\xff", b" " * 8193):
                path.write_bytes(raw)
                with self.assertRaises(Fault):
                    bundled_client(path)


class BundleAccountTest(EngineCase):
    def test_clean_default_uses_bundled_client_for_authorization_and_refresh(self):
        self.journal.set("active_client", None)
        public = {"client_id": CLIENT, "client_secret": CLIENT_SECRET}
        with patch("omadocs.accounts.bundled_client", return_value=public), \
                patch.object(self.oauth, "authorize", wraps=self.oauth.authorize) as authorize, \
                patch.object(self.oauth, "refresh", wraps=self.oauth.refresh) as refresh:
            account = self.accounts.authorize(label="Release test")
            self.accounts.token(account, force=True)
            self.assertEqual(authorize.call_args.args[0], public)
            self.assertEqual(refresh.call_args.args[0], public)
            self.assertTrue(self.engine.status()["setup"]["client_configured"])
            self.assertTrue(self.engine.diagnostics()["production_client"])
        self.assertNotIn(CLIENT_SECRET, json.dumps(self.journal.rows("SELECT * FROM accounts")))
        self.assertEqual(self.journal.account(self.account)["client"], "test-client")

    def test_custom_client_takes_precedence(self):
        with patch("omadocs.accounts.bundled_client") as packaged:
            key, client = self.accounts.current_client()
        packaged.assert_not_called()
        self.assertEqual(key, "test-client")
        self.assertEqual(client, {"client_id": CLIENT})

    def test_invalid_bundle_does_not_report_ready(self):
        self.journal.set("active_client", None)
        with patch("omadocs.accounts.bundled_client", side_effect=Fault("credentials_required")):
            self.assertFalse(self.engine.status()["setup"]["client_configured"])
            self.assertFalse(self.engine.diagnostics()["production_client"])
            with self.assertRaises(Fault):
                self.accounts.current_client()
