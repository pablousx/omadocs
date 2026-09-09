import ast
import io
import json
import os
from pathlib import Path
import tarfile
import uuid
from unittest.mock import patch
from omadocs.cli import support_bundle
from omadocs.desktop import Mime
from omadocs.errors import Fault
from omadocs.google import read_desktop_credentials
from omadocs.ipc import validate, decode, envelope, Dispatcher, MAX_MESSAGE
from tests.base import EngineCase
from tests.fakes import office, ACCESS, REFRESH, CODE, CLIENT, CLIENT_SECRET


class IPCTest(EngineCase):
    def test_valid_requests(self):
        for method, params in (("status", {}), ("open", {"files": ["/tmp/a b.docx"]}), ("accounts.rename", {"id": self.account, "label": "Work"}), ("settings.set", {"key": "choose_account", "value": True})):
            self.assertEqual(validate(envelope(method, params))["params"], params)

    def test_reject_unsupported_fields_types_and_secrets(self):
        values = [envelope("open", {"files": []}), envelope("open", {"files": ["/tmp/a"] * 65}), envelope("open", {"files": ["relative.docx"]}),
                  envelope("open", {"files": [1]}), envelope("status", {"access_token": ACCESS}), envelope("execute", {"command": "rm -rf"}),
                  envelope("accounts.rename", {"id": "../../etc", "label": "bad"}), envelope("settings.set", {"key": "x", "value": "true"})]
        v = envelope("status"); v["version"] = True; values.append(v)
        v = envelope("status"); v["surprise"] = 1; values.append(v)
        for value in values:
            with self.subTest(value=value["method"]), self.assertRaises(Fault):
                validate(value)

    def test_malformed_wire_messages(self):
        for value in (b"{", b'{"a":1,"a":2}', b'{"x":NaN}', b"x" * (MAX_MESSAGE + 1), b"\xff"):
            with self.assertRaises(Fault):
                decode(value)

    def test_dispatcher_methods_are_allowlisted(self):
        dispatch = Dispatcher(self.engine, Mime(self.paths, self.journal, query=lambda _: ""))
        self.assertIn("accounts", dispatch.dispatch(envelope("status")))
        with self.assertRaises(Fault):
            dispatch.dispatch(envelope("__getattribute__", {"name": "keyring"}))


class LeakTest(EngineCase):
    def test_credentials_and_session_never_in_public_surfaces(self):
        key = self.open(office(self.root / "private-contract.docx"))
        # Inject an exception containing every secret; only its fixed code escapes.
        def leak_attempt(call):
            if call["method"] == "PUT":
                raise RuntimeError(" ".join((ACCESS, REFRESH, CODE, CLIENT_SECRET)))
        self.google.before = leak_attempt
        self.engine.run(key)
        status = self.engine.status()
        diag = self.engine.diagnostics()
        target = self.root / "support.tar.gz"
        support_bundle(target, diag)
        surfaces = [json.dumps(status).encode(), json.dumps(diag).encode()]
        for path in self.paths.state.iterdir():
            if path.is_file():
                surfaces.append(path.read_bytes())
        with tarfile.open(target) as bundle:
            self.assertEqual(bundle.getnames(), ["diagnostics.json"])
            surfaces.append(bundle.extractfile("diagnostics.json").read())
        for value in surfaces:
            for secret in (ACCESS, REFRESH, CODE, CLIENT_SECRET, "TEST-SESSION-SECRET-SENTINEL"):
                self.assertNotIn(secret.encode(), value)
        diagnostics_bytes = json.dumps(diag).encode()
        for private in ("private-contract", "owner@example.test", str(self.root)):
            self.assertNotIn(private.encode(), diagnostics_bytes)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_custom_client_import_does_not_persist_file_or_secret(self):
        path = self.root / "credentials.json"
        path.write_text(json.dumps({"installed": {"client_id": CLIENT, "client_secret": CLIENT_SECRET}}))
        result = self.accounts.import_client(path)
        self.assertTrue(result["imported"])
        for file in self.paths.state.iterdir():
            if file.is_file():
                self.assertNotIn(CLIENT_SECRET.encode(), file.read_bytes())
                self.assertNotIn(str(path).encode(), file.read_bytes())
        self.assertIn(CLIENT_SECRET, json.dumps(self.keyring.values))

    def test_web_or_endpoint_overridden_credentials_rejected(self):
        path = self.root / "credentials.json"
        for value in ({"web": {"client_id": CLIENT}}, {"installed": {"client_id": CLIENT, "token_uri": "https://evil.test"}}, {"installed": {"client_id": CLIENT, "refresh_token": REFRESH}}):
            path.write_text(json.dumps(value))
            with self.assertRaises(Fault):
                read_desktop_credentials(path)

    def test_support_bundle_no_overwrite_and_no_arbitrary_files(self):
        p = self.root / "existing"
        p.write_text("keep")
        with self.assertRaises(FileExistsError):
            support_bundle(p, self.engine.diagnostics())
        self.assertEqual(p.read_text(), "keep")
        with self.assertRaises(Fault):
            support_bundle(self.root / "bad", {"token": ACCESS})

    def test_subprocess_sites_use_arrays_no_shell_or_token_transport(self):
        root = Path(__file__).resolve().parents[1] / "omadocs"
        sites = 0
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                    if node.func.attr in ("run", "Popen"):
                        sites += 1
                        self.assertIsInstance(node.args[0], ast.List, str(path))
                        self.assertFalse(any(k.arg == "shell" for k in node.keywords), str(path))
                        call_source = ast.get_source_segment(path.read_text(), node)
                        self.assertNotIn("access_token", call_source)
                        self.assertNotIn("refresh_token", call_source)
                        self.assertNotIn("client_secret", call_source)
        self.assertGreater(sites, 0)

    def test_qml_has_no_secret_transport_or_shell_execution(self):
        root = Path(__file__).resolve().parents[1]
        for path in root.glob("*.qml"):
            source = path.read_text()
            for forbidden in ("access_token", "refresh_token", "client_secret", "execDetached", '"bash"', '"sh"', '.run('):
                self.assertNotIn(forbidden, source, str(path))
