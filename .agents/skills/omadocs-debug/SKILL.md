---
name: omadocs-debug
description: Diagnose and fix omadocs UI, helper, OAuth, uploads, file picker, MIME handling, and installed-version problems. Use for failures in this plugin; not general Linux desktop customization.
---

# Debug omadocs

Read root `AGENTS.md`, `docs/troubleshooting.md`, and the relevant section of `docs/architecture.md`. Paths below are repository-relative.

## Establish the failing layer

Record the reproduction, expected behavior, safe error code, and whether it affects the checkout or installed runtime. Start with:

```bash
./omadocs-run diagnostics --json
omarchy plugin list --json
```

The CLI may start the helper on demand; these are diagnostic commands, not an offline file reader. Status and accounts output can contain identities and document names, unlike redacted diagnostics. Inspect only what is needed and do not paste private output into reports.

Inspect the installed `~/.config/omarchy/plugins/io.github.pablousx.omadocs/manifest.json`, development marker, and (for Git installations) Git status/HEAD/origin. A development manifest points inside `runtime/<digest>/`; root repository source paths are not proof of what the shell loaded. Match the actual runtime before diagnosing a supposedly missing fix.

## Follow symptoms to evidence

| Symptom | Investigation and recovery |
| --- | --- |
| Stale or unloaded UI | Run QML/UI checks; inspect installed entry points. Reinstall this checkout with `scripts/install-local.py` for an owned development copy. For a Git install use the publishing skill's update procedure. Rescan with `omarchy-shell shell rescanPlugins` if needed. |
| UI pending/error/focus bug | Trace `UiAction.qml`, `BridgeState.qml`, `UiLogic.js`, and the relevant view against `tests/qml/`. Add a behavioral regression scenario. |
| Helper Busy after update | Active uploads/authorization intentionally prevent replacement. Let them settle; do not clear locks, delete state, or kill active uploads to force a new build. |
| Keyring/auth failure | Check session Secret Service availability/unlock and the safe fault code. Reauthenticate when appropriate. Distinguish bundled configuration, imported per-account client, revoked consent, and account identity mismatch. Never dump keyring contents or capture OAuth callbacks. |
| Missing production client | Validate `assets/oauth-client.json` with `scripts/check-release.py`; do not assume this old troubleshooting condition describes the current bundle. Read `docs/oauth-adr.md`. |
| Retry/uncertain upload | Trace persisted operation state and original Drive ID reconciliation in `engine.py`/`google.py`, using fakes. Retry the existing activity when authorized; repeating Open creates another copy. Never delete a remote file or replace the ID as a recovery shortcut. |
| Upload succeeded, browser failed | Preserve upload success; Reopen uses the existing link. Browser Google session selection is outside the helper's control. Editor versus viewer is observed behavior, not guaranteed. |
| Rejected local file | Check URI syntax, regular-file/no-symlink constraints, Office package type, encryption, permissions and snapshot space. Do not bypass these checks or upload a user's private document to reproduce. |
| Picker hangs/crashes | Trace `FilePicker.qml` → launcher `_pick` → `omadocs/picker.py`. Check zenity and child completion/cancellation. Keep dialog toolkit code outside Quickshell. |
| MIME/launcher failure | Start with `./omadocs-run mime status`, inspect ownership/backups and manifest resolution in `desktop.py`. Preserve manually changed defaults/files; consult `docs/uninstall.md` before removal. |

Inspect only relevant time-bounded shell messages, for example `journalctl --user -t omarchy-shell --since '10 minutes ago'`, locally. Separate this plugin's errors from other widgets. If a core dump needs investigation, use the available diagnose-crash skill; secret-bearing helper core dumps are intentionally disabled. Do not enable dumps to collect credentials.

For shareable diagnostics, create a new nonexisting path outside the repository:

```bash
./omadocs-run support-bundle --output /tmp/omadocs-support.tar.gz
```

If that path exists, choose a new name. The bundle contains only redacted diagnostics. Do not attach raw journals, databases, snapshots, OAuth JSON, browser URLs, or keyring exports. Sending a report is a separate authorized action.

## Prove the fix

Reproduce against the smallest relevant fake-service Python or QtTest scenario, implement the fix, and run the checks selected by the development skill. Broaden testing for persistence, protocol, security, or lifecycle changes. Do not treat fake tests as evidence of Google consent, refresh, or editor landing behavior.

Real uploads require intended disposable files and an authorized live-validation task. User login/consent stays manual. `scripts/check-desktop.py` changes real MIME defaults temporarily and belongs only to intentional desktop validation. Record the confirmed cause, changed behavior, checks, and remaining uncertainty; update troubleshooting only for reusable findings.
