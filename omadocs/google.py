"""Fixed Google endpoints, installed-app OAuth, and resumable binary uploads."""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import random
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass
from .errors import Fault
from .files import open_regular

SCOPE = "https://www.googleapis.com/auth/drive.file"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
CLIENT_RE = re.compile(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com\Z")
ID_RE = re.compile(r"[A-Za-z0-9_-]{8,200}\Z")
MAX_RESPONSE = 1024 * 1024


def validate_url(value, purpose="view", expected_id=None):
    if not isinstance(value, str) or len(value) > 8192 or not value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise Fault("invalid_response")
    try:
        u = urllib.parse.urlsplit(value)
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or u.fragment:
            raise Fault("invalid_response")
        if re.search(r"%(?![0-9A-Fa-f]{2})", value) or re.search(r"%(?:0[0-9A-Fa-f]|1[0-9A-Fa-f]|7[fF])", value):
            raise Fault("invalid_response")
        if purpose == "view":
            if u.hostname == "drive.google.com":
                valid = bool(re.fullmatch(r"/file/d/[A-Za-z0-9_-]+/(?:view|edit|preview)", u.path)) or u.path == "/open"
            elif u.hostname == "docs.google.com":
                valid = bool(re.fullmatch(r"/(?:document|spreadsheets|presentation)/d/[A-Za-z0-9_-]+/(?:edit|view|preview)", u.path))
            else:
                valid = False
            if not valid:
                raise Fault("invalid_response")
            if u.path == "/open":
                ids = urllib.parse.parse_qs(u.query).get("id", [])
                if len(ids) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", ids[0]):
                    raise Fault("invalid_response")
                link_id = ids[0]
            else:
                link_id = u.path.split("/d/", 1)[1].split("/", 1)[0]
            if expected_id is not None and link_id != expected_id:
                raise Fault("invalid_response")
        elif purpose == "session":
            q = urllib.parse.parse_qs(u.query, strict_parsing=True)
            if u.hostname != "www.googleapis.com" or u.path != "/upload/drive/v3/files" or q.get("uploadType") != ["resumable"] or len(q.get("upload_id", [])) != 1:
                raise Fault("invalid_response")
        else:
            raise Fault("internal")
    except (ValueError, TypeError):
        raise Fault("invalid_response") from None
    return value


def open_browser(url, *, authorization=False):
    if authorization:
        if not url.startswith(AUTH_URL + "?"):
            raise Fault("auth_browser")
    else:
        validate_url(url)
    try:
        result = subprocess.run(["xdg-open", url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20, check=False)
        if result.returncode:
            raise Fault("auth_browser" if authorization else "browser")
    except (OSError, subprocess.TimeoutExpired):
        raise Fault("auth_browser" if authorization else "browser") from None


def summon_panel():
    from . import PLUGIN_ID
    try:
        subprocess.run(["omarchy-shell", "shell", "summon", PLUGIN_ID, "{}"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes

    def json(self):
        try:
            data = json.loads(self.body)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, UnicodeError):
            raise Fault("invalid_response") from None


class Transport:
    def request(self, method, url, *, headers=None, data=None, json_body=None):
        import requests
        # A separate session per request avoids shared mutable session state and
        # environment proxies/netrc. Redirects never receive bearer headers.
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.request(method, url, headers=headers, data=data, json=json_body,
                                     timeout=(10, 60), allow_redirects=False, stream=True) as response:
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE:
                            raise Fault("invalid_response")
                    return Response(response.status_code, {k.lower(): v for k, v in response.headers.items()}, bytes(body))
        except requests.RequestException:
            raise Fault("offline", retryable=True) from None


def response_fault(response):
    status = response.status
    retry_after = 0
    try:
        retry_after = float(response.headers.get("retry-after", 0))
    except (ValueError, TypeError):
        pass
    if status == 401:
        return Fault("authentication")
    if status == 429:
        return Fault("quota", retryable=True, retry_after=retry_after)
    if 500 <= status < 600:
        return Fault("offline", retryable=True, retry_after=retry_after)
    if status == 403:
        try:
            reasons = {e.get("reason") for e in response.json().get("error", {}).get("errors", []) if isinstance(e, dict)}
        except (Fault, AttributeError, TypeError):
            reasons = set()
        if reasons & {"rateLimitExceeded", "userRateLimitExceeded", "sharingRateLimitExceeded"}:
            return Fault("quota", retryable=True, retry_after=retry_after)
        if "storageQuotaExceeded" in reasons or "dailyLimitExceeded" in reasons:
            return Fault("quota")
        return Fault("permission")
    return Fault("invalid_response")


def backoff(attempt, fault, sleep=time.sleep, rng=random.uniform):
    sleep(min(60, max(fault.retry_after, rng(0, min(32, 2 ** attempt)))))


class OAuth:
    def __init__(self, transport=None, browser=open_browser):
        self.transport = transport or Transport()
        self.browser = browser

    def _tokens(self, form):
        response = self.transport.request("POST", TOKEN_URL, data=form)
        if response.status != 200:
            if response.status in (400, 401):
                raise Fault("authentication")
            raise response_fault(response)
        data = response.json()
        if not isinstance(data.get("access_token"), str) or not data["access_token"] or not isinstance(data.get("token_type"), str) or data["token_type"].lower() != "bearer":
            raise Fault("invalid_response")
        if "scope" in data and set(str(data["scope"]).split()) != {SCOPE}:
            raise Fault("permission")
        try:
            if type(data.get("expires_in")) is bool:
                raise ValueError
            expiry = int(data["expires_in"])
            if not 0 < expiry <= 86400:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise Fault("invalid_response") from None
        result = {"access_token": data["access_token"], "expires_at": time.time() + expiry}
        if "refresh_token" in data:
            if not isinstance(data["refresh_token"], str) or not data["refresh_token"]:
                raise Fault("invalid_response")
            result["refresh_token"] = data["refresh_token"]
        return result

    def refresh(self, client, saved):
        if not saved or not saved.get("refresh_token"):
            raise Fault("authentication")
        form = {"client_id": client["client_id"], "refresh_token": saved["refresh_token"], "grant_type": "refresh_token"}
        if client.get("client_secret"):
            form["client_secret"] = client["client_secret"]
        tokens = self._tokens(form)
        tokens.setdefault("refresh_token", saved["refresh_token"])
        return tokens

    def authorize(self, client, *, timeout=180):
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(32)
        callback_path = "/callback/" + secrets.token_urlsafe(16)
        result = {}
        finished = threading.Event()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                # Never log or reflect request targets: they contain the code.
                valid = False
                try:
                    url = urllib.parse.urlsplit(self.path)
                    q = urllib.parse.parse_qs(url.query, strict_parsing=True, max_num_fields=12)
                    valid = (len(self.path) <= 8192 and url.path == callback_path and
                             self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}" and
                             len(q.get("state", [])) == 1 and secrets.compare_digest(q["state"][0], state) and
                             not finished.is_set())
                    if valid:
                        if "error" in q:
                            result["error"] = True
                        elif len(q.get("code", [])) == 1 and 0 < len(q["code"][0]) <= 4096:
                            result["code"] = q["code"][0]
                        else:
                            valid = False
                except (ValueError, TypeError):
                    valid = False
                body = b"Return to omadocs. You can close this tab." if valid else b"Invalid callback."
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass
                if valid:
                    finished.set()

            def setup(self):
                self.request.settimeout(2)
                super().setup()

        class Server(http.server.HTTPServer):
            def handle_error(self, request, client_address):
                pass

        with Server(("127.0.0.1", 0), Handler) as server:
            server.timeout = 0.25
            redirect = f"http://127.0.0.1:{server.server_port}{callback_path}"
            url = AUTH_URL + "?" + urllib.parse.urlencode({
                "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
                "scope": SCOPE, "code_challenge": challenge, "code_challenge_method": "S256",
                "state": state, "access_type": "offline", "prompt": "consent select_account",
                "include_granted_scopes": "false",
            })
            # Serve during browser startup too: some default handlers wait.
            stop = threading.Event()
            def listen():
                while not stop.is_set() and not finished.is_set():
                    server.handle_request()
            thread = threading.Thread(target=listen, daemon=True)
            thread.start()
            try:
                self.browser(url, authorization=True)
                if not finished.wait(timeout) or "code" not in result:
                    raise Fault("auth_cancelled")
            finally:
                stop.set()
                thread.join(3)
        form = {"client_id": client["client_id"], "code": result.pop("code"), "code_verifier": verifier,
                "grant_type": "authorization_code", "redirect_uri": redirect}
        if client.get("client_secret"):
            form["client_secret"] = client["client_secret"]
        tokens = self._tokens(form)
        if not tokens.get("refresh_token"):
            raise Fault("authentication")
        return tokens


def read_desktop_credentials(path):
    fd = open_regular(path)
    try:
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise Fault("invalid_input")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"installed"}:
            raise Fault("invalid_input")
        obj = data["installed"]
        if not isinstance(obj, dict) or not CLIENT_RE.fullmatch(obj.get("client_id", "")):
            raise Fault("invalid_input")
        allowed = {"client_id", "client_secret", "project_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url", "redirect_uris"}
        if not obj.keys() <= allowed or obj.get("auth_uri", AUTH_URL) not in (AUTH_URL, "https://accounts.google.com/o/oauth2/auth") or obj.get("token_uri", TOKEN_URL) != TOKEN_URL:
            raise Fault("invalid_input")
        result = {"client_id": obj["client_id"]}
        if "client_secret" in obj:
            if not isinstance(obj["client_secret"], str) or not 1 <= len(obj["client_secret"]) <= 4096:
                raise Fault("invalid_input")
            result["client_secret"] = obj["client_secret"]
        return result
    except (OSError, ValueError, TypeError):
        raise Fault("invalid_input") from None


class Drive:
    def __init__(self, token, transport=None, sleep=time.sleep):
        self.token = token
        self.transport = transport or Transport()
        self.sleep = sleep

    def call(self, method, url, *, allowed=(200,), retry=True, **kwargs):
        refreshed = False
        force_refresh = False
        for attempt in range(6):
            try:
                headers = dict(kwargs.pop("headers", {})) if attempt == 0 else headers
                headers["Authorization"] = "Bearer " + self.token(force=force_refresh)
                force_refresh = False
                response = self.transport.request(method, url, headers=headers, **kwargs)
                if response.status in allowed:
                    return response
                if response.status == 401 and not refreshed:
                    refreshed = True
                    force_refresh = True
                    continue
                raise response_fault(response)
            except Fault as exc:
                if not retry or not exc.retryable or attempt == 5:
                    raise
                backoff(attempt, exc, self.sleep)
        raise Fault("authentication")

    def identity(self):
        obj = self.call("GET", API + "/about?fields=user(permissionId,emailAddress,displayName)").json().get("user")
        if not isinstance(obj, dict) or not all(isinstance(obj.get(k), str) and obj[k] for k in ("permissionId", "emailAddress")):
            raise Fault("invalid_response")
        if len(obj["permissionId"]) > 200 or len(obj["emailAddress"]) > 320 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", obj["emailAddress"]):
            raise Fault("invalid_response")
        return obj

    def generate_id(self):
        values = self.call("GET", API + "/files/generateIds?count=1&space=drive&type=files").json().get("ids")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or not ID_RE.fullmatch(values[0]):
            raise Fault("invalid_response")
        return values[0]

    def metadata(self, operation):
        key = operation["drive_id"]
        if not key or not ID_RE.fullmatch(key):
            raise Fault("invalid_response")
        fields = "id,mimeType,size,md5Checksum,webViewLink,appProperties,ownedByMe,owners(permissionId,emailAddress)"
        response = self.call("GET", API + "/files/" + key + "?" + urllib.parse.urlencode({"fields": fields}), allowed=(200, 404))
        return None if response.status == 404 else response.json()

    def initiate(self, operation):
        meta = {"id": operation["drive_id"], "name": operation["name"], "mimeType": operation["mime"],
                "appProperties": {"omadocsOperation": operation["id"]}}
        response = self.call("POST", UPLOAD + "?uploadType=resumable", allowed=(200, 409), json_body=meta,
                             headers={"X-Upload-Content-Type": operation["mime"], "X-Upload-Content-Length": str(operation["size"])})
        if response.status == 409:
            return None
        return validate_url(response.headers.get("location"), "session")

    def progress(self, session, size):
        response = self.call("PUT", validate_url(session, "session"), allowed=(200, 201, 308, 404, 410),
                             headers={"Content-Length": "0", "Content-Range": f"bytes */{size}"}, data=b"")
        return self._upload_result(response, size)

    def chunk(self, session, offset, data, size, mime):
        end = offset + len(data) - 1
        response = self.call("PUT", validate_url(session, "session"), allowed=(200, 201, 308, 404, 410), retry=False,
                             headers={"Content-Type": mime, "Content-Length": str(len(data)),
                                      "Content-Range": f"bytes {offset}-{end}/{size}"}, data=data)
        return self._upload_result(response, size)

    @staticmethod
    def _upload_result(response, size):
        if response.status in (404, 410):
            return {"expired": True}
        if response.status in (200, 201):
            return {"complete": True}
        value = response.headers.get("range")
        if value is None:
            return {"offset": 0}
        match = re.fullmatch(r"bytes=0-([0-9]+)", value)
        if not match or not 0 < int(match[1]) + 1 <= size:
            raise Fault("invalid_response")
        return {"offset": int(match[1]) + 1}
