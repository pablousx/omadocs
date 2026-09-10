# Development

All project sources live in this repository root. The Python package is `omadocs/`; it is not a nested project. Run the executable `./omadocs-run` without packaging or virtualenv setup. Python dependencies are declared in `pyproject.toml`; on Omarchy use the system packages documented in the README. Tests use the standard library's `unittest`.

For pull request CI, branch protections, maintainer bypass, and reusable ruleset templates, see [repository rules](repository-rules.md).

## Checks

```bash
python -m unittest discover -s tests -v
python scripts/check-qml.py
python scripts/check-ui.py
omarchy plugin validate .
```

The suite uses fake OAuth/Drive/keyring/browser implementations, real loopback callbacks to those fake flows, real Unix sockets, isolated XDG desktop associations, and process-death tests. It needs local socket binding, which some agent sandboxes restrict. It does not contact Google or change the user's MIME defaults. The fake classes are in `tests/` and are never selected by a production command or endpoint environment variable.

The QML checker creates a temporary `qs` import alias outside the repository because Quickshell supplies that virtual module mapping at runtime. It uses the installed Omarchy sources and fails on QML warnings as well as errors. No packaged files are modified, and there are no symlinks in the plugin tree.

## UI interaction checks

`python scripts/check-ui.py` runs 22 behavioral/rendering scenarios (QtTest reports 28 passes including fixture setup/cleanup). It uses the real bridge state, presentation logic, and view components with Qt Controls stand-ins for Quattro’s theme widgets. Quickshell embeds its QML plugins in its executable, so an ordinary offscreen QtTest runner cannot load the full native shell toolkit. These tests validate interaction behavior, not native theme appearance. They fail on QML warnings and use only fake accounts/files; no helper or Google requests are started.

Native appearance, panel keyboard shortcuts, and the isolated `zenity` picker are checked separately in the running shell. `FilePicker.qml` invokes the private `_pick` launcher mode in its own process. Do not reintroduce QtQuick.Dialogs into the shell: native GTK3/GVFS dialog code aborted Quickshell during local testing. The picker’s process result is handled after stdout completion; cancellation returns to the panel and submits no upload.

The chooser child uses `GIO_USE_VFS=local` and `GDK_DEBUG=no-portals` for local files. This avoids the portal cancellation hang reproduced on this machine; it does not change the desktop environment or other applications. See the official [GIO environment documentation](https://docs.gtk.org/gio/overview.html) and [GTK runtime options](https://docs.gtk.org/gtk4/running.html).

## Local shell validation

```bash
python scripts/install-local.py
omarchy-shell shell summon io.github.pablousx.omadocs '{}'
omarchy-shell shell hide io.github.pablousx.omadocs
```

The installer only replaces a development copy marked as belonging to this checkout. Its installed manifest points to a versioned copy of the exact runtime sources. That avoids stale failed-component caching observed during Quattro 4.0.3 testing. Source remains in the repository; no second Quickshell instance is launched.

Desktop launchers resolve the current runtime through the installed manifest, so a development update does not leave file associations pointing at a deleted version. On startup, the helper also refreshes unchanged, omadocs-owned launcher and desktop files to migrate older installations. It preserves MIME preferences, restoration backups, and manually edited launchers.

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
