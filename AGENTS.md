# Maintaining omadocs

omadocs is an Omarchy Quattro shell plugin with a Python helper and a static GitHub Pages site. Run commands from this repository root. The distributable plugin uses `manifest.json`; it is not a Codex plugin and does not use a Codex marketplace or cachebuster.

## Task instructions

Read the matching repository skill before doing the work. These files also work as direct instructions if your agent does not discover repository skills automatically:

- Development, UI, backend, tests: [.agents/skills/omadocs-develop/SKILL.md](.agents/skills/omadocs-develop/SKILL.md).
- Bugs, stale installs, authentication, upload recovery, desktop integration: [.agents/skills/omadocs-debug/SKILL.md](.agents/skills/omadocs-debug/SKILL.md).
- Releases, published plugin updates, installation smoke tests, website deployment: [.agents/skills/omadocs-publish/SKILL.md](.agents/skills/omadocs-publish/SKILL.md).

Read only relevant supporting documents. Keep these instructions and the affected documentation current when a workflow or contract changes. Prefer the actual scripts and workflow definitions over historical test counts or readiness statements.

## Project map

| Area | Sources |
| --- | --- |
| Shell entry points | `manifest.json`, `Service.qml`, `BarWidget.qml` |
| Panel and interaction | `Panel.qml`, `*View.qml`, `UiAction.qml`, `UiText.qml`, `NotificationFooter.qml`, `FilePicker.qml` |
| UI transport and state | `Bridge.qml`, `BridgeState.qml`, `UiLogic.js` |
| CLI, IPC, lifecycle | `omadocs-run`, `omadocs/cli.py`, `omadocs/ipc.py`, `omadocs/__init__.py` |
| Upload state and persistence | `omadocs/engine.py`, `journal.py`, `files.py`, `paths.py` |
| Google and credentials | `omadocs/google.py`, `accounts.py`, `secrets.py`, `errors.py` |
| Desktop integration | `omadocs/desktop.py`, `picker.py` |
| Checks and fixtures | `scripts/check-*.py`, `tests/`, `tests/qml/` |
| Public site | `site/`, `.github/workflows/pages.yml` |

## Contracts to preserve

- Each new Open creates a new Drive copy. Retry retains the original operation and Drive ID; Reopen only launches the saved link. No synchronization, downloads, conversion, folder routing, remote deletion, or local file overwrite.
- Only `drive.file` access and operation-owned Drive IDs. Preserve account ownership through retries and reauthentication; never silently fall back to another account.
- Commit upload success before browser launch. Preserve reconciliation of uncertain remote writes and browser handoffs across process death.
- Tokens, codes, and resumable session URLs stay out of QML, SQLite, logs, command arguments, environment, and support bundles. Secret Service has no plaintext fallback. `assets/oauth-client.json` is the approved public Desktop application configuration; do not print its values or add other credential files.
- Keep file snapshots private, IPC bounded and validated, subprocess arguments structured, and diagnostics redacted. Consult `docs/architecture.md`, `docs/threat-model.md`, and `docs/oauth-adr.md` when changing these boundaries.
- Use the existing shell process and external picker. Do not introduce `QtQuick.Dialogs` into Quickshell, launch a second shell, or edit packaged `/usr/share/omarchy` files.

## Working practice

Inspect `git status --short` before edits and preserve unrelated work. Use focused behavioral tests for changes; documentation-only edits need link/skill validation and publication checks, not an unrelated full runtime test run. Report checks actually executed, environmental blockers, and live behavior still unverified.

Local implementation and validation do not authorize publication, real Google uploads, MIME-default changes, or unrelated desktop changes. Follow the user's existing authorization without asking again. Prepare the concrete release/diff/check results before seeking any missing publication approval. Normally use a PR and passing checks; a maintainer bypass is not the default workflow. See `docs/repository-rules.md`.

## Common checks

```bash
python -m unittest discover -s tests -v
python scripts/check-qml.py
python scripts/check-ui.py
omarchy plugin validate .
python scripts/check-site.py
python scripts/check-release.py
```

Python requires 3.12+; dependencies are in `pyproject.toml` and `README.md`. Native QML checks require installed Omarchy/Qt. `check-desktop.py` is a separate opt-in real-user MIME test, not part of this routine check block. See the development skill for test selection and environment requirements.
