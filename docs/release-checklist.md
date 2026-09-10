# Release checklist

## Code and local validation

- [ ] Run the complete automated suite and record the exact count/results.
- [ ] Run `python scripts/check-release.py` against the final publication tree; use `--custom-setup` only for a release explicitly requiring user-provided credentials.
- [ ] Pass `python scripts/check-ui.py` and test native picker selection/cancellation, keyboard focus, and inline recovery actions.
- [ ] Pass `python scripts/check-qml.py` without warnings and `omarchy plugin validate .`.
- [ ] Validate the generated desktop entry with `desktop-file-validate`.
- [ ] Exercise isolated and guarded real MIME installation/restoration, including later user changes.
- [ ] Inspect the installed panel, keyboard navigation, all three main views and the four Settings sections, theme changes, multiple monitors, long names, and bounded activity scrolling.
- [ ] Inspect this plugin's QML messages and redacted helper events. Do not claim unrelated shell warnings are omadocs failures.
- [ ] Review every changed file for sync/download/list/revision/folder-routing code, shell command construction, tokens/codes/session URLs in public surfaces, and unintended artifacts.
- [ ] Verify no symlinks, user tokens, downloaded OAuth credential JSON (the explicitly approved public Desktop client bundle is allowed), document fixtures containing private content, support archives, or databases are in the release tree.
- [ ] Verify all source is directly in this repository, and the manifest uses `io.github.pablousx.omadocs` with schema version 1.

## Google production gates

- [ ] Provision the maintainer-owned Desktop client and Drive API.
- [ ] Complete project-specific consent/branding/privacy/production requirements.
- [ ] Validate the packaged Desktop client PKCE/loopback and refresh flow with the actual production client. Version 0.1.0 bundles both approved Desktop application fields after client-ID-only refresh failed; exact-bundle refresh passed. Fresh-user browser consent remains unverified.
- [ ] Test clean users without their own Cloud project.
- [ ] Test refresh, revoked/expired authentication, multiple upload accounts, and identity mismatch on reauthentication.
- [ ] Confirm only `drive.file` is requested and only created file IDs are accessed.
- [ ] Upload disposable DOCX/XLSX/PPTX files, verify owner/MIME/size/checksum, and preserve local bytes/mtime.
- [ ] Manually record whether each returned `webViewLink` opens an editor or needs Open with. Do not infer this from documentation or fake tests.
- [ ] Confirm Reopen performs no upload and does not claim browser-session control.

## Distribution

- [ ] Review license, README, ADR, threat model, troubleshooting, development/uninstall instructions, and screenshot checklist.
- [ ] Record remaining limitations honestly in `docs/validation.md`.
- [ ] Obtain explicit permission before publishing the Git repository, tagging/pushing a release, or submitting to a plugin directory.
- [ ] After authorized publication, test `omarchy plugin add <repository-url> --enable` in a clean Quattro user profile and test update/removal.

A development build with no maintainer client or no live validation must not be advertised as a fully validated production release.
