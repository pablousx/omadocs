"""Opt-in local Quattro UI fixture; all accounts/documents/services are fake.

Run while the production plugin is disabled and its helper is stopped:
  python -m tests.ui_demo /tmp/omadocs-ui-fixture
Then enable the installed development plugin. Stop this fixture with the
normal helper shutdown RPC before returning to the production helper.
Nothing is written to the user's real journal, keyring, or MIME defaults.
"""
import sys
from pathlib import Path
import uuid
from omadocs.accounts import Accounts
from omadocs.desktop import Mime, DESKTOP_ID, MIMES
from omadocs.engine import Engine
from omadocs.google import Drive
from omadocs.ipc import serve
from omadocs.journal import Journal
from omadocs.paths import Paths
from tests.fakes import FakeGoogle, FakeOAuth, MemoryKeyring, CLIENT, office


def demo_components(paths):
    journal = Journal(paths.state / "journal.sqlite3")
    keyring, google = MemoryKeyring(), FakeGoogle()
    google.email = "alice@example.test"
    accounts = Accounts(journal, keyring, FakeOAuth(), lambda token: Drive(token, google, sleep=lambda _: None))
    keyring.put("client/demo", {"client_id": CLIENT})
    journal.set("active_client", "demo")
    alice = accounts.authorize(label="DEMO Personal")
    google.identity_id, google.email = "demo-work", "work@example.test"
    work = accounts.authorize(label="DEMO Work")
    journal.execute("UPDATE accounts SET enabled=0 WHERE id=?", (work,))
    google.identity_id, google.email = "account-identity-1", "alice@example.test"
    engine = Engine(paths, journal, keyring, accounts=accounts, browser=lambda _: None,
                    summon=lambda: None, sleep=lambda _: None, autostart=False)
    def add(name, choose=False):
        source = office(paths.cache / name)
        return engine.open([str(source)], str(uuid.uuid4()), choose=choose)["operations"][0]["id"]
    finished = add("DEMO Informe México.docx")
    engine.run(finished)
    browser_failed = add("DEMO Budget.xlsx")
    engine.run(browser_failed)
    journal.update(browser_failed, browser="failed")
    add("DEMO Choose account.pptx", choose=True)
    progress = add("DEMO Large report.docx")
    journal.update(progress, state="uploading", progress=journal.operation(progress)["size"] // 2)
    auth = add("DEMO Authentication.xlsx")
    journal.update(auth, state="auth_required", error="authentication")
    mime = Mime(paths, journal, query=lambda m: "demo-office.desktop")
    return journal, engine, mime


def main():
    root = Path(sys.argv[1]).absolute()
    # Own persistent data is isolated; the normal runtime socket lets the exact,
    # unmodified QML/bridge sources connect to this explicitly launched fixture.
    real = Paths.user()
    paths = Paths(root / "state", root / "cache", real.runtime, root / "config", root / "data", root / "bin")
    return serve(paths, components=demo_components)


if __name__ == "__main__":
    raise SystemExit(main())
