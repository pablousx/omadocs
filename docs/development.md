# Development

All project sources live in this repository root. The Python package is `omadocs/`; it is not a nested project. Run the executable `./omadocs-run` without packaging or virtualenv setup. Python dependencies are declared in `pyproject.toml`; on Omarchy use the system packages documented in the README. Tests use the standard library's `unittest`.

## Checks

```bash
python -m unittest discover -s tests -v
python scripts/check-qml.py
omarchy plugin validate .
```

The suite uses fake OAuth/Drive/keyring/browser implementations, real loopback callbacks to those fake flows, real Unix sockets, isolated XDG desktop associations, and process-death tests. It needs local socket binding, which some agent sandboxes restrict. It does not contact Google or change the user's MIME defaults. The fake classes are in `tests/` and are never selected by a production command or endpoint environment variable.

The QML checker creates a temporary `qs` import alias outside the repository because Quickshell supplies that virtual module mapping at runtime. It uses the installed Omarchy sources and fails on QML warnings as well as errors. No packaged files are modified, and there are no symlinks in the plugin tree.

## Local shell validation

```bash
python scripts/install-local.py
omarchy-shell shell summon io.github.pablousx.omadocs '{}'
omarchy-shell shell hide io.github.pablousx.omadocs
```

The installer only replaces a development copy marked as belonging to this checkout. Its installed manifest points to a versioned copy of the exact runtime sources. That avoids stale failed-component caching observed during Quattro 4.0.3 testing. Source remains in the repository; no second Quickshell instance is launched.

The helper uses a single user runtime socket. A code fingerprint permits an idle helper to stop for replacement after an update; it refuses replacement while uploads or authorization are active. Python bytecode writes are disabled in the launcher so helper imports do not cause plugin file-watch reloads.

A guarded **real-user** MIME test is separate from the automated suite:

```bash
python scripts/check-desktop.py
```

It refuses an existing omadocs MIME setup, records the current handlers immediately before installation, and restores them in `finally`. Run it only when intentionally validating desktop integration. It retains normal durable backups if restoration cannot complete.

## Live validation

Complete every non-live check first. Then provide the helper only a local path to a maintainer-owned Desktop OAuth JSON file:

```bash
./omadocs-run credentials import /absolute/path/to/desktop-client.json
./omadocs-run accounts add --label 'Live validation'
```

The authorization browser requires the user's Google login/consent. Do not automate it or capture callback URLs/codes. Use small, disposable local test files created specifically for validation; upload one of each format and observe the returned link manually. Verify ownership, original MIME, local checksum/mtime, browser launch, refresh, account selection, and reopening. Do not download Drive data to perform a comparison. The API's returned MD5 and size provide the upload-integrity check.

Record each format's actual landing behavior (editor or viewer requiring Open with), browser name/version, date, and consent/client mode in the validation document without account emails, file IDs, codes, tokens, or private paths. Never mark live behavior as passed from fake-service results.

Before release, separately test the bundled public-client-only production configuration and a clean install using `omarchy plugin add <repository-url> --enable`. Publishing the repository or updating the marketplace requires maintainer permission.
