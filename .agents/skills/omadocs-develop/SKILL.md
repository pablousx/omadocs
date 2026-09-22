---
name: omadocs-develop
description: Develop omadocs Python, QML, desktop integration, tests, and static website content. Use for changes in this Omarchy plugin repository; use omadocs-publish for distribution and deployment.
---

# Develop omadocs

Read root `AGENTS.md` and `docs/development.md`. Paths below are relative to the repository root. Inspect the current diff before changing files.

## Setup and implementation

Use Python 3.12+ and `./omadocs-run`; there is no required packaging/build step. Runtime requirements are `requests`, `SecretStorage`, `xdg-utils`, a session Secret Service, and Omarchy Quattro. The picker uses `zenity`. Follow `pyproject.toml` and README for versions/packages. CI's system Python also needs PyGObject/GLib and `desktop-file-utils` for desktop tests; inspect `.github/workflows/ci.yml` before reproducing CI elsewhere.

Trace the affected boundary before editing:

- UI: view/action → bridge state and presentation → JSON bridge → IPC dispatcher. Keep asynchronous pending/error states, selection, focus, and rename drafts stable during updates. Use theme widgets and shared text/action components already present.
- Backend: CLI and panel share the dispatcher. Follow `docs/architecture.md` for operation state, locks, persistence, and account ownership. Update the protocol's validation and callers together when changing a method.
- Google/security: read `docs/oauth-adr.md` and `docs/threat-model.md`. Production does not select fake adapters through environment variables. Keep test doubles in `tests/`.
- Desktop: preserve MIME backups, subsequent user choices, and user-edited generated files. Keep the picker in a child process; retain its local-VFS/portal workarounds unless a replacement is demonstrated safe.
- Website: read `docs/website.md`. Edit plain HTML/CSS/JS in `site/`, preserve relative URLs for `/omadocs/`, no-JavaScript content, both themes, and no external runtime resources. Keep claims aligned with observed validation.

## Select validation

| Change | Checks |
| --- | --- |
| Python behavior | Focused `python -m unittest tests.test_engine -v` (substitute relevant module), then full discovery for cross-cutting behavior |
| QML or UI logic | `python scripts/check-qml.py`, `python scripts/check-ui.py`; native shell review for appearance, focus, picker, or shell integration |
| Manifest/runtime packaging | `omarchy plugin validate .`, `python scripts/check-release.py` |
| Desktop | `tests.test_desktop`, `tests.test_xdg`, `tests.test_picker`, as relevant; live MIME test only when intentionally requested |
| Site | `python scripts/check-site.py`, browser review for changed layouts/interactions |
| Release | Complete gates in the publishing skill and `docs/release-checklist.md` |

The full Python command is `python -m unittest discover -s tests -v`. Tests use fake services, temporary state, real local sockets and process-death scenarios. Socket-denied sandbox errors require an environment permitting local sockets; do not weaken the tests or label those failures product regressions without evidence.

`check-qml.py` supplies a temporary virtual `qs` import using the installed shell (`OMARCHY_PATH` can override its root). It rejects warnings. `check-ui.py` runs offscreen QtTest with stand-ins for native widgets, so it cannot establish native appearance. Derive counts from current output rather than copying historical documentation.

Preview the website with `python -m http.server 8765 --directory site --bind 127.0.0.1`. Check changed pages, keyboard access, narrow widths, both themes, and relevant JavaScript fallbacks; stop the server when finished.

## Run changed code in the desktop

When local installation is within scope, run:

```bash
python scripts/install-local.py
omarchy-shell shell summon io.github.pablousx.omadocs '{}'
omarchy-shell shell hide io.github.pablousx.omadocs
```

The installer copies root QML/JS, launcher, Python package, and assets into a content-addressed runtime and rewrites installed entry points. It replaces only a development copy whose `.omadocs-development-source` identifies this checkout. Respect a refusal: inspect the existing installation instead of deleting it. New runtime directories/files must be added to the installer's source selection when needed.

Reinstall after source changes; editing this checkout alone does not change the installed copy. Fresh component paths avoid stale QML caching. The helper replaces itself only when idle, preserving ongoing uploads/authentication. Do not kill active work to refresh code. Never use a Codex version suffix for this workflow.

For native fixtures/screenshots, read `tests/ui_demo.py`, `docs/screenshot-checklist.md`, and any current `docs/screenshots/README.md` first. The fixture uses fake persistent data but the normal runtime socket: production must be disabled and its helper stopped safely before starting it. Shut the fixture down before returning to production. Screenshots must use fictional accounts/documents.

Update affected user docs and validation limitations with the implementation. Report what changed, actual check results, and any native/live behavior not exercised.
