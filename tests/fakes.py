"""Test-only Google and keyring services; unreachable from production CLI."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.parse
import zipfile
from omadocs.errors import Fault
from omadocs.files import FORMATS
from omadocs.google import Response, API, UPLOAD, TOKEN_URL, SCOPE

ACCESS = "TEST-ACCESS-SECRET-SENTINEL-aA19"
REFRESH = "TEST-REFRESH-SECRET-SENTINEL-bB29"
CODE = "TEST-CODE-SECRET-SENTINEL-cC39"
CLIENT_SECRET = "TEST-CLIENT-SECRET-SENTINEL-dD49"
CLIENT = "123456789-testclient.apps.googleusercontent.com"


class MemoryKeyring:
    def __init__(self):
        self.values = {}
        self.lock = threading.RLock()
        self.locked = False

    def get(self, key):
        with self.lock:
            if self.locked:
                raise Fault("keyring")
            return copy.deepcopy(self.values.get(key))

    def put(self, key, value):
        with self.lock:
            if self.locked:
                raise Fault("keyring")
            self.values[key] = copy.deepcopy(value)

    def delete(self, key):
        with self.lock:
            if self.locked:
                raise Fault("keyring")
            self.values.pop(key, None)

    def delete_all(self):
        self.values.clear()


class FakeOAuth:
    def __init__(self):
        self.refreshes = 0
        self.error = None
        self.refresh_error = None

    def authorize(self, client):
        if self.error:
            raise self.error
        return {"access_token": ACCESS, "refresh_token": REFRESH, "expires_at": time.time() + 3600}

    def refresh(self, client, saved):
        self.refreshes += 1
        if self.refresh_error:
            raise self.refresh_error
        return {"access_token": ACCESS, "refresh_token": REFRESH, "expires_at": time.time() + 3600}


def office(path, size=16, suffix=None):
    suffix = suffix or Path(path).suffix.lower()
    mime, main, content = FORMATS[suffix]
    xml = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/' + main + '" ContentType="' + content + '"/></Types>').encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml", xml)
        z.writestr(main, b"<document/>" + b" " * size)
    return Path(path)


class FakeGoogle:
    def __init__(self):
        self.files = {}
        self.sessions = {}
        self.calls = []
        self.generated = 0
        self.identity_id = "account-identity-1"
        self.email = "owner@example.test"
        self.lock = threading.RLock()
        self.before = None
        self.after = None
        self.token_error = None
        self.token_body = None
        self.metadata_override = None

    def response(self, status=200, body=None, headers=None):
        return Response(status, headers or {}, json.dumps(body).encode() if body is not None else b"")

    def request(self, method, url, *, headers=None, data=None, json_body=None):
        # These are fake wire records, never production logs/support bundles.
        with self.lock:
            call = {"method": method, "url": url, "headers": dict(headers or {}), "data": data, "json": copy.deepcopy(json_body)}
            self.calls.append(call)
            if self.before:
                response = self.before(call)
                if response is not None:
                    return response
            response = self._request(method, url, headers or {}, data, json_body)
            if self.after:
                override = self.after(call, response)
                if override is not None:
                    return override
            return response

    def _request(self, method, url, headers, data, body):
        if url == TOKEN_URL:
            if self.token_error:
                return self.response(self.token_error, {"error": "invalid_grant"})
            return self.response(body=self.token_body or {"access_token": ACCESS, "refresh_token": REFRESH, "token_type": "Bearer", "expires_in": 3600, "scope": SCOPE})
        if headers.get("Authorization") != "Bearer " + ACCESS:
            return self.response(401)
        u = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/drive/v3/about":
            return self.response(body={"user": {"permissionId": self.identity_id, "emailAddress": self.email, "displayName": "Fake user"}})
        if u.path == "/drive/v3/files/generateIds":
            self.generated += 1
            return self.response(body={"ids": ["generated-file-" + str(self.generated)]})
        if method == "GET" and u.path.startswith("/drive/v3/files/"):
            key = u.path.split("/")[-1]
            if key not in self.files:
                return self.response(404)
            meta = copy.deepcopy(self.files[key])
            if self.metadata_override:
                meta = self.metadata_override(meta)
            return self.response(body=meta)
        if method == "POST" and url.startswith(UPLOAD):
            if body["id"] in self.files:
                return self.response(409)
            session_id = "TEST-SESSION-SECRET-SENTINEL-" + str(len(self.sessions) + 1)
            self.sessions[session_id] = {"meta": copy.deepcopy(body), "bytes": bytearray(), "size": int(headers["X-Upload-Content-Length"])}
            return self.response(headers={"location": UPLOAD + "?uploadType=resumable&upload_id=" + session_id})
        if method == "PUT" and url.startswith(UPLOAD):
            key = q["upload_id"][0]
            if key not in self.sessions:
                return self.response(404)
            session = self.sessions[key]
            if session["meta"]["id"] in self.files:
                return self.response(body=self.files[session["meta"]["id"]])
            if headers.get("Content-Length") == "0":
                count = len(session["bytes"])
                return self.response(308, headers={"range": f"bytes=0-{count-1}"} if count else {})
            match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", headers["Content-Range"])
            offset, end, total = map(int, match.groups())
            assert offset == len(session["bytes"]), "client must probe offset before retransmission"
            assert end + 1 - offset == len(data)
            session["bytes"].extend(data)
            if len(session["bytes"]) == total:
                meta = session["meta"]
                self.files[meta["id"]] = dict(meta, size=str(total), md5Checksum=hashlib.md5(session["bytes"], usedforsecurity=False).hexdigest(),
                                             ownedByMe=True, owners=[{"permissionId": self.identity_id, "emailAddress": self.email}],
                                             webViewLink="https://drive.google.com/file/d/" + meta["id"] + "/view")
                return self.response(200, body=self.files[meta["id"]])
            return self.response(308, headers={"range": f"bytes=0-{end}"})
        raise AssertionError("Unexpected Google endpoint: " + method + " " + u.path)

    def stats(self):
        return {"files": len(self.files), "generated": self.generated, "calls": len(self.calls)}
