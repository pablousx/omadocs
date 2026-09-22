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

## Follow-up: stock-style panel simplification

Date: 2026-09-22. The panel was simplified against the installed Omarchy 4.0.4 network and Bluetooth panels: its content width is now 380 theme pixels, the decorative status card is replaced by the standard icon/title/status hero and `PanelSeparator`, section labels use the stock uppercase hierarchy, and actions use denser monochrome rectangular controls. Upload, account, Settings, notification, keyboard, and accessibility behavior is unchanged.

- The three views passed the existing UI interaction/render suite (**28 QtTest passes**) and QML validation completed without warnings.
- Uploads, Accounts, and Settings were inspected in the running shell against the isolated fake-account fixture. The review covered progress, authentication recovery, account choice, paused accounts, tab selection, toggle layout, collapsed Settings sections, separators, and vertical scrolling. No horizontal clipping or overlap was observed at the new width.
- Temporary full-desktop captures were kept outside the repository; only fictional fixture data was used. The fixture was shut down before returning to the normal helper.

During repeated shell reloads, Quickshell once crashed in Qt/QML delegate-model destruction after reporting an IPC-requested exit. System crash history showed the same shutdown signature before this change, and the core contained no omadocs frame or source reference. The shell restarted and reconnected to the installed plugin. This is recorded as an environmental shutdown limitation, not hidden or treated as evidence of a plugin-specific regression.

## Follow-up: desktop launch after development update

The user subsequently reported successful credential import and Google account linking, followed by a DOCX open that produced no activity. Inspection reproduced a local `FileNotFoundError`: the desktop launcher referred to the runtime directory removed by the icon update. No upload operation had reached the helper.

The launcher now resolves the active runtime through the installed manifest. Helper startup repairs unchanged, owned desktop resources without changing MIME preferences. Three regression tests cover launching after deletion of the previous runtime, retaining restoration behavior and intervening default changes, and preserving modified or absent launchers. **82 tests passed** after this fix. The installed launcher passed `--version` and reached redacted diagnostics, which confirmed one linked account; MIME settings checksums were unchanged. Retrying the user's DOCX and observing the Google landing page remain pending.

## Follow-up: UX revision

The user subsequently confirmed that opening the document works. This is user-reported DOCX success; XLSX, PPTX, and detailed browser landing behavior have not been independently observed.

The panel now has three destinations: Uploads, Accounts, and Settings. Uploads provides a file chooser, attention/active/recent filters, progress, account selection, and contextual recovery actions. Accounts has guided setup, inline editing, and confirmation before removal. Settings groups infrequent tasks in expandable sections. Actions have independent busy states, duplicate-click protection, acknowledgement-based feedback, keyboard focus, and recoverable errors. Background updates preserve input drafts and row identity.

- **89 Python tests passed**, including seven file-picker cases. The picker subset passed again after the final child-environment adjustment.
- **18 UI scenarios passed** (22 QtTest passes including setup/cleanup): action acknowledgements/errors, duplicate clicks, disconnect behavior, independent busy states, stable row identity/focus, filters, progress formatting, browser failure presentation, credential drafts, account management, and cancellation confirmation. These tests use real view/bridge logic with theme stand-ins, not Google services.
- All three redesigned tabs were visually inspected in the native shell theme. Settings sections default to collapsed. Screenshots remain outside the repository because they include private desktop context.
- QML validation passed without warnings against installed Quattro imports, and the root manifest validated successfully.
- Native dialog testing exposed a GTK3/GVFS crash when embedding QtQuick.Dialogs in Quickshell. That implementation was removed. The final picker runs in a separate process, with a local chooser that avoids a subsequently reproduced desktop portal cancellation hang. A native open/Escape test returned `{"cancelled": true}` and exited normally, without submitting a file.
- The installed panel’s own Upload files → Escape flow was also verified: cancellation reopened the panel, restored the enabled Upload files button, and left the existing upload unchanged. No plugin-specific QML warnings/errors appeared in the final installation log check.

The linked account and existing completed upload were preserved. No additional live upload was used for this UX validation.

## Follow-up: stable notification footer

Date: 2026-09-09. Removed the permanent Drive-copy sentence and moved panel notifications below the page into a reserved two-line footer. Message changes, dismissal, and setup-button visibility cannot change the footer height. Truncated text is available in a hover tooltip; notification priority and existing actions are preserved.

The UI suite passed 22 scenarios (28 QtTest passes including fixture setup/cleanup), including unchanged content/footer geometry across all three pages for empty, success, reconnecting, sign-in, and long-error states, plus tooltip and footer action checks. QML and manifest validation passed.

## Release preparation — September 9, 2026

The maintainer reports that the Google Cloud project has been published to production. The repository `pablousx/omadocs` is publicly readable, and its permanent plugin ID remains unchanged.

- **94 Python tests passed**, including five new bundled-client parsing, default-selection, custom-client precedence, refresh, and readiness checks. The **22 UI scenarios** (28 QtTest passes), QML validation, site checks, and root manifest validation passed.
- Live token refresh with the already connected account returned HTTP 400 `invalid_request` when only the client ID was supplied. The otherwise identical request using the existing Desktop client's `client_secret` succeeded. No credential values were printed, no account data was overwritten, and this check did not upload files or validate a new user's consent flow.
- The bundled-client loader now accepts only a bounded `client_id` and optional Desktop application `client_secret`. Readiness checks validate the bundle instead of treating any existing file as configured. Custom client precedence and existing account associations are preserved.
- No production OAuth bundle has been written yet: publishing the Desktop `client_secret` differs from the earlier client-ID-only plan and awaits the maintainer's explicit choice. The release checker refuses a built-in-sign-in release without a valid bundle.
- The publication tree and existing Git history passed credential-signature checks. `preview.png` was generated from the project website with fictional files and accounts. The marketplace submission draft uses Productivity with bar/quickshell tags; no existing submission was found.
- Git transport works, but the saved GitHub CLI token is invalid. GitHub release creation and marketplace submission await renewed CLI authentication. No release commit, tag, push, or marketplace issue was created during this preparation.

## Version 0.1.0 publication validation — September 9, 2026

The earlier dated records describe the state at each validation stage. They do not supersede this publication record.

The maintainer authorized publication after reviewing Desktop client reuse and billing risks. The approved `client_id` and Desktop application `client_secret` were extracted from omadocs' configured client into `assets/oauth-client.json`; no user credentials or tokens were included. Live refresh with this exact bundle passed without replacing the existing account's stored tokens. GitHub authentication is working and the maintainer's remote `CNAME` commit was incorporated without overwriting it. Cloud billing settings were not inspected or changed.

The built-in path is covered by the automated bundle/default/refresh tests. A fresh user's Google consent with the packaged release, live XLSX/PPTX browser behavior, and installation in a separate clean Quattro profile remain unverified. Version 0.1.0 is an initial release with those documented limitations, not a claim of complete production certification.

Final pre-publication checks passed: **94 Python tests** (5.840 seconds), **22 UI scenarios / 28 QtTest passes**, QML validation without warnings, root manifest validation, static site checks, release artifact/credential checks, and `git diff --check`. No tests were skipped.


## Version 0.1.1 UI release validation — September 10, 2026

This release updates the native panel width, typography, monochrome header icon, buttons, links, list separators, and tinted notification footer. The Close button is removed; Escape and outside-click dismissal remain the panel's dismissal controls. Upload/account/credential/MIME contracts are unchanged.

- **94 Python tests passed**, with no skipped tests, including desktop entry validation, isolated MIME round trips, and the external picker tests. The system PyGObject emitted a deprecation warning in a desktop test; the test passed.
- **28 QtTest passes** (including fixture setup/cleanup), with view rendering and notification layout checked at a 408-pixel content width for the 440-pixel panel.
- QML validation passed without warnings, along with plugin validation, static site validation, repository configuration checks, and release artifact/credential checks.
- Refreshed [native captures](screenshots/README.md) use fictional accounts and documents, including upload progress, browser failure, the account list, Settings, and a dismissible error. All four Settings sections were opened for visual review. The theme-scaled panel measured 513 pixels wide in this desktop session.
- Native Ctrl+2 navigation, Escape dismissal, and external picker Escape cancellation/reopening passed in the existing shell with a temporary fake bridge. An initial attempt encountered a preview focus/IPC interruption during shell reload; the checks passed after the shell settled. The temporary preview was removed afterward.
- This pass did not independently exercise every theme/monitor orientation, long-name combination, or native picker selection. No real Google upload, new consent/reauthentication, or real-user MIME-default mutation was performed. Existing 0.1.0 limitations remain: fresh-user Google consent, live XLSX/PPTX browser landing behavior, and installation in a separate clean Quattro user profile are unverified.
- The website's source version is updated to 0.1.1; Pages deployment is separate and is not part of this plugin release.

## Version 0.1.2 panel release validation — September 22, 2026

This release candidate narrows the panel to 380 theme pixels and adopts Omarchy's compact header, section labels, separators, and denser neutral actions. It does not change upload, account, OAuth, file, MIME, or persistence behavior. The permanent plugin ID remains `io.github.pablousx.omadocs`.

- **94 Python tests passed** outside the filesystem/network sandbox, with no skipped tests. The sandboxed attempt was intentionally disregarded because local socket creation and multiprocessing were denied; all eight sandbox-only socket failures passed in the unrestricted rerun.
- **28 QtTest passes**, QML validation without warnings, official plugin validation, static-site checks, release checks, and `git diff --check` passed.
- The development plugin was reinstalled before capture and reported version 0.1.2 from runtime digest `8a6b82e0c9eccd67`. Uploads, uploaded copies, account management, paused-account recovery, Settings, keyboard tab switching, and authentication/account-choice states were inspected in the installed panel.
- Refreshed repository captures contain only fictional fixture accounts and files and crop exactly to the panel. `preview.png` matches the uploaded-copies capture. No full-desktop image was added.
- No live Google request, new consent flow, upload, or real-user MIME-default change was performed. The MIME association files retained their pre-test SHA-256 values, and the isolated UI fixture did not use the real journal or keyring. Fresh-user consent and live XLSX/PPTX browser landing behavior remain unverified.
- Distribution archive, extracted-package, reproducibility, PR/CI, Pages, GitHub Release, and marketplace verification are separate gates to be completed against the final reviewed commit. Nothing in this 0.1.2 preparation record constitutes publication.
