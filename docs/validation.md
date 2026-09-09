# Local validation record

Date: 2026-09-08. This record distinguishes fake-service testing from live Google observation.

## Environment

- Omarchy 4.0.3-1 / Quickshell 0.3.1-1, using the existing shell process.
- Python 3.14.7, requests 2.34.2, SecretStorage 3.5.0.
- Secret Service provided by the user's login keyring.
- Repository source lives directly in `/home/pablousx/dev/omadocs`. The environment exposes an empty read-only `.git` stub, so there is no usable Git metadata or Git diff; the complete newly created source tree was reviewed instead.

## Completed checks

- **79 automated tests passed**, including fake OAuth and Drive, actual local OAuth callback handling, real helper Unix sockets/processes, snapshot validation/cleanup, account actions, concurrent admissions/uploads, and credential-leak checks.
- The process-death test includes **seven separate crash boundaries**: generated-ID response, durable ID commit, resumable-session response, intermediate chunk commit, remote upload completion, local completion commit, and browser handoff. Recovery produced exactly one fake remote file per operation.
- Real `xdg-mime` installation/restoration passed in isolated XDG directories. Native GLib desktop launching preserved spaces, Unicode, quotes, dollar signs, backticks, and percent characters; GLib may deliver local URIs as decoded paths, and both forms are supported.
- Generated desktop entries passed `desktop-file-validate`.
- `python scripts/check-qml.py` passed without warnings against the installed Quattro imports.
- `omarchy plugin validate .` passed for the repository root.
- The plugin was copied into the user-owned plugin directory and loaded/enabled in the existing Quickshell shell. The empty Accounts panel was visually inspected in the current theme.
- Final reload testing caught a late pipe callback during QML destruction. The bridge now starts after component completion, stops reconnecting during destruction, and guards late callbacks. A subsequent disable/enable cycle produced zero plugin warning/error lines; the normal helper reported no demo accounts or operations and all required dependencies available.
- A populated, isolated fake-account helper was connected to the unmodified installed QML. It supplied two fake accounts and activity states for upload progress, authentication required, account selection, completion, and browser failure. Account rename, Reopen, Settings, and redacted Diagnostics passed through the real RPC interface. Recent plugin-specific QML error count was zero. Later populated-panel screen capture returned a blank image, so it is not represented as a successful screenshot or a complete visual pass of every tab/theme.
- A **real-user MIME round trip** installed all three handlers, verified each, and restored the defaults recorded immediately before the test. Those defaults were `onlyoffice_desktop_editors.desktop` for all three formats. Earlier inspection had shown LibreOffice; restoration correctly honored the newer choices.
- A **real Secret Service canary** write/read/delete succeeded. Its value was never printed, and cleanup was verified. This was not Google OAuth validation.
- Source review and automated AST/sentinel checks found no shell-command execution, token/code persistence in public surfaces, or synchronization/download/revision/folder-routing implementation. No plugin source was written under `/usr/share/omarchy`, and no additional Quickshell instance was started.

The isolated UI fixture was shut down before returning to the normal helper. It did not modify the user's real journal, Secret Service credentials, or MIME defaults. Screenshots remained outside the repository because they contained unrelated desktop content or were blank.

## Live Google validation: not performed

No live Desktop OAuth credential file was supplied, and no maintainer client ID is bundled. Fake results do not establish production Google OAuth behavior.

| Format | Live upload / ownership | Returned link landing behavior |
| --- | --- | --- |
| DOCX | Not tested | Not observed: editor versus viewer/Open with remains pending |
| XLSX | Not tested | Not observed: editor versus viewer/Open with remains pending |
| PPTX | Not tested | Not observed: editor versus viewer/Open with remains pending |

Remaining release gates are maintainer-owned Desktop client provisioning, production consent/branding configuration, public-client-only OAuth validation, live account/refresh/upload checks, and manual observation of each returned Office link. A remote `omarchy plugin add <repository-url> --enable` clone has not been tested because this repository has not been published; its root manifest and local installation path were validated.

See the release and screenshot checklists for broader release certification. Nothing was published.
