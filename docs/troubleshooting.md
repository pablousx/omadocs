# Troubleshooting

Start with `./omadocs-run diagnostics --json` (or `omadocs diagnostics --json` after MIME installation). The panel's Diagnostics section shows the same safe data. Helper events are fixed codes, not raw network logs.

| Symptom | Action |
| --- | --- |
| Production OAuth client not configured | This development build has no maintainer client yet. For development, import a Desktop JSON file outside the repository, then Add account. Normal releases must bundle a validated maintainer public client ID. |
| Authentication/keyring error | Unlock the login keyring; ensure `org.freedesktop.secrets` is available on the user session bus. Reauthenticate if Google revoked/expired the refresh token. Never create a plaintext fallback. |
| Authorization rejected by Google | Check Desktop client type, Drive API enablement, consent/test-user configuration, and Workspace administrator policy. Expired Testing-mode tokens are expected to need renewed consent. |
| Wrong account in the browser | Read the Owner in upload activity, then switch to that account in Google's UI. omadocs does not control browser sessions or profiles. |
| Google viewer opens instead of editor | Choose Google's Open with action. The helper preserves the Office format and opens the returned link. Live format-specific behavior is recorded separately. |
| Offline / quota / permission | Resolve the indicated condition, then Retry the activity. Retry reuses its Google ID. Repeating Open creates a new intentional copy. |
| Local-file error | Use an unencrypted DOCX/XLSX/PPTX with a matching package type. Check free disk space and permissions. Symlinks and non-regular files are intentionally rejected. Save active edits before reopening. |
| Temporary copy missing/expired | The helper cannot safely resume the original bytes. It will not silently reread the source. If status is Unresolved, Retry checks only the original owned Google ID; Cancel explicitly abandons the operation. Check Drive/activity before intentionally opening a new copy. |
| Uploaded but browser failed/uncertain | Use Reopen. Upload success is preserved and no new copy is created. |
| Account removal reports Busy | A snapshot, authorization, or network request is still settling. Cancellation is checked at request/chunk boundaries. Wait for status to settle and retry Remove. |
| Handler setup failed | Check `mime status`, your user-config permissions, and whether an unrelated `~/.local/bin/omadocs` exists. Do not overwrite it. Run `mime remove` to finish a partial restoration before retrying. |
| UI shows an old development build | Run `python scripts/install-local.py`. It gives the installed runtime a fresh QML component path. Do not start a second Quickshell process or edit packaged Omarchy code. |
| Helper update reports Busy | Let active uploads/authorization finish. The helper replaces itself only when idle; old uploads keep their original state. |

Validate the repository with:

```bash
python -m unittest discover -s tests -v
python scripts/check-qml.py
omarchy plugin validate .
```

Inspect Quattro runtime messages locally with `journalctl --user -t omarchy-shell`; search for this plugin ID and distinguish unrelated plugins' warnings. Do not attach an entire shell journal to a support report. Instead, create a redacted bundle:

```bash
./omadocs-run support-bundle --output /tmp/omadocs-support.tar.gz
```

The target must not already exist. The archive contains only `diagnostics.json`. Never attach OAuth JSON files, copied keyring entries, snapshots, raw databases, or browser callback URLs.
