import base64
import hashlib
import json
import threading
import urllib.parse
import urllib.request
import unittest
from unittest.mock import patch
from omadocs.errors import Fault
from omadocs.google import OAuth, Drive, Response, SCOPE, TOKEN_URL, validate_url, response_fault, backoff, open_browser
from tests.fakes import FakeGoogle, ACCESS, REFRESH, CODE, CLIENT


class GoogleURLTest(unittest.TestCase):
    def test_supported_returned_links(self):
        for value in ("https://drive.google.com/file/d/abc123/view?usp=drivesdk", "https://drive.google.com/open?id=abc123", "https://docs.google.com/document/d/abc/edit", "https://docs.google.com/spreadsheets/d/abc/edit", "https://docs.google.com/presentation/d/abc/edit"):
            self.assertEqual(validate_url(value), value)

    def test_disallowed_links(self):
        values = ("http://drive.google.com/file/d/abc/view", "https://drive.google.com.evil.test/file/d/abc/view", "https://docs.google.com@evil.test/document/d/a/edit",
                  "https://user@docs.google.com/document/d/a/edit", "https://docs.google.com:444/document/d/a/edit", "javascript:alert(1)",
                  "file:///etc/passwd", "https://drive.google.com/redirect?next=evil", "https://docs.google.com/document/d/a/edit#token=secret",
                  "https://docs.google.com/document/d/a/edit\n", "https://docs.google.com/document/d/a/edit?x=%0aevil", "https://drive.google.com\\@evil/file/d/a/view")
        for value in values:
            with self.subTest(value=value), self.assertRaises(Fault):
                validate_url(value)

    def test_session_url_validation(self):
        good = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=secret"
        self.assertEqual(validate_url(good, "session"), good)
        for bad in (good.replace("www.googleapis.com", "evil.test"), good.replace("uploadType=resumable", "uploadType=media"), "http://127.0.0.1/session", good.replace("/upload/drive/v3/files", "/other")):
            with self.assertRaises(Fault):
                validate_url(bad, "session")

    def test_browser_argv_no_shell(self):
        url = "https://drive.google.com/file/d/test/view"
        with patch("omadocs.google.subprocess.run") as run:
            run.return_value.returncode = 0
            open_browser(url)
            self.assertEqual(run.call_args.args[0], ["xdg-open", url])
            self.assertNotIn("shell", run.call_args.kwargs)


class OAuthTest(unittest.TestCase):
    def test_pkce_loopback_and_scope(self):
        transport = FakeGoogle()
        observed = {}
        def browser(url, *, authorization=False):
            self.assertTrue(authorization)
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            observed.update(q)
            self.assertEqual(q["scope"], [SCOPE])
            self.assertEqual(q["code_challenge_method"], ["S256"])
            callback = q["redirect_uri"][0]
            self.assertEqual(urllib.parse.urlsplit(callback).hostname, "127.0.0.1")
            with urllib.request.urlopen(callback + "?" + urllib.parse.urlencode({"state": q["state"][0], "code": CODE}), timeout=3) as response:
                self.assertNotIn(CODE.encode(), response.read())
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        tokens = OAuth(transport, browser).authorize({"client_id": CLIENT}, timeout=2)
        self.assertEqual(tokens["refresh_token"], REFRESH)
        exchange = transport.calls[-1]["data"]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(exchange["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(challenge, observed["code_challenge"][0])
        self.assertEqual(exchange["code"], CODE)
        self.assertEqual(exchange["redirect_uri"], observed["redirect_uri"][0])

    def test_wrong_state_is_rejected_then_valid_callback_works(self):
        transport = FakeGoogle()
        def browser(url, **_):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            callback = q["redirect_uri"][0]
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(callback + "?state=wrong&code=" + CODE, timeout=3)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
            with urllib.request.urlopen(callback + "?" + urllib.parse.urlencode({"state": q["state"][0], "code": CODE}), timeout=3) as response:
                response.read()
        self.assertIn("access_token", OAuth(transport, browser).authorize({"client_id": CLIENT}, timeout=2))

    def test_timeout_and_denial(self):
        with self.assertRaises(Fault) as error:
            OAuth(FakeGoogle(), lambda *_, **__: None).authorize({"client_id": CLIENT}, timeout=0.01)
        self.assertEqual(error.exception.code, "auth_cancelled")
        def deny(url, **_):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            with urllib.request.urlopen(q["redirect_uri"][0] + "?" + urllib.parse.urlencode({"state": q["state"][0], "error": "access_denied"}), timeout=3) as response:
                response.read()
        with self.assertRaises(Fault) as error:
            OAuth(FakeGoogle(), deny).authorize({"client_id": CLIENT}, timeout=2)
        self.assertEqual(error.exception.code, "auth_cancelled")

    def test_refresh_keeps_refresh_token(self):
        google = FakeGoogle()
        google.token_body = {"access_token": ACCESS, "expires_in": 3600, "token_type": "Bearer"}
        tokens = OAuth(google).refresh({"client_id": CLIENT}, {"refresh_token": REFRESH})
        self.assertEqual(tokens["refresh_token"], REFRESH)

    def test_extra_scope_and_malformed_token_response(self):
        google = FakeGoogle()
        oauth = OAuth(google)
        for obj in ({"access_token": ACCESS, "expires_in": 3600, "token_type": "Bearer", "scope": SCOPE + " email"},
                    {"access_token": ACCESS, "expires_in": -1, "token_type": "Bearer"}, {"token_type": "Bearer", "expires_in": 3600}, {"access_token": ACCESS, "token_type": 7, "expires_in": 3600}, {"access_token": ACCESS, "token_type": "Bearer", "expires_in": True}):
            google.token_body = obj
            with self.assertRaises(Fault):
                oauth.refresh({"client_id": CLIENT}, {"refresh_token": REFRESH})


class DriveTest(unittest.TestCase):
    def test_bounded_backoff(self):
        calls = []
        for n in range(10):
            backoff(n, Fault("quota", retry_after=500), calls.append, lambda lo, hi: hi)
        self.assertEqual(calls, [60] * 10)

    def test_retry_limit(self):
        google = FakeGoogle()
        google.before = lambda _: google.response(503)
        sleeps = []
        drive = Drive(lambda **_: ACCESS, google, sleeps.append)
        with self.assertRaises(Fault):
            drive.generate_id()
        self.assertEqual(len(google.calls), 6)
        self.assertEqual(len(sleeps), 5)

    def test_error_classification(self):
        for status, body, code in ((401, {}, "authentication"), (403, {}, "permission"), (403, {"error": {"errors": [{"reason": "storageQuotaExceeded"}]}}, "quota"), (429, {}, "quota"), (503, {}, "offline"), (302, {}, "invalid_response")):
            self.assertEqual(response_fault(Response(status, {}, json.dumps(body).encode())).code, code)

    def test_invalid_offsets_and_response_json(self):
        for header in ("garbage", "bytes=8-9", "bytes=0-100", "bytes=0--1"):
            with self.assertRaises(Fault):
                Drive._upload_result(Response(308, {"range": header}, b""), 100)
        for value in (b"[1,2]", b"not json", b"null", b"\xff"):
            with self.assertRaises(Fault):
                Response(200, {}, value).json()

    def test_401_refresh_is_only_performed_once(self):
        google = FakeGoogle()
        requested = []
        attempts = [0]
        def token(**kwargs):
            requested.append(kwargs["force"])
            return ACCESS
        def error(call):
            attempts[0] += 1
            if attempts[0] == 1:
                return google.response(401)
            if attempts[0] == 2:
                return google.response(503)
        google.before = error
        Drive(token, google, sleep=lambda _: None).generate_id()
        self.assertEqual(requested, [False, True, False])
