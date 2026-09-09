# Threat model

## Assets and trust boundaries

Protect user OAuth credentials, temporary document bytes, account selection, source integrity, and ownership of new Drive copies. Inputs include local paths/URIs, ZIP package metadata, IPC requests, OAuth callbacks, Google responses, browser launch results, and desktop association files.

Quattro plugins share an unsandboxed QML scene and run with the user's permissions. The helper boundary prevents **this plugin** from putting tokens into that scene. It is not an isolation boundary against malicious code already running as the same user, root, a compromised browser, or a compromised Secret Service. A same-user process may also call the private socket or keyring. Peer UID checks protect against other users, not hostile peers with identical credentials.

## Controls

| Threat | Control |
| --- | --- |
| Shell/argument injection through filenames or labels | No shell evaluation, explicit argument arrays, strict command schemas, `--` before desktop-supplied files, Desktop Entry escaping, plain-text QML rendering. |
| Symlink races, devices, FIFOs, sockets | Descriptor-based component traversal with `O_NOFOLLOW`, regular-file checks, nonblocking source open, private exclusive snapshot creation. |
| Source mutation during an upload | Upload a private snapshot; reflink or bounded streaming copy, before/after source metadata checks, checksum verification before upload. The source is never written. |
| ZIP/XML bombs or hostile package structure | Bound central directory/entry/XML sizes, forbid XML entity declarations, reject encrypted entries, duplicate/traversal members and incompatible Office types; no arbitrary extraction or macro execution. |
| Duplicate files after retries/crashes | Durable pre-generated Drive ID, private operation marker, resumable status probes, owner/size/checksum verification, same-ID reconciliation. |
| OAuth callback injection or replay | Loopback-only listener, random path/port, strong state, S256 PKCE, single accepted callback, bounded requests/timeouts, no callback logging or reflection. |
| Bearer-token exfiltration through URLs | Fixed Google API/token endpoints; HTTPS; no redirects; environment proxies/netrc disabled; strict resumable-session and returned-view URL validation. |
| Tokens in UI, logs, database, support artifacts | Helper-only secret handling, Secret Service-only persistence, fixed error codes, suppressed HTTP logging, allowlisted diagnostics, secret sentinels in automated tests. |
| Debug/core-dump leakage | Disable core dumps and Linux dumpability before serving; sanitized top-level and thread failures. |
| Accidental account switching | Default account pinned at admission; no fallback; identity verification on reauthentication; owner displayed separately from local label. |
| Uninstall overwriting newer MIME choices | Conditional per-MIME restoration and content hashes on generated files. |

## Residual limitations

- Private temporary snapshots are not additionally encrypted by omadocs. Filesystem encryption, swap protection, browser storage, and physical access remain system concerns. Deleting a snapshot is not a promise of secure media erasure.
- Python cannot guarantee complete memory zeroization. Credentials necessarily exist in helper memory while used. It never persists them outside Secret Service.
- Source modification checks detect ordinary concurrent edits; an adversarial filesystem or same-user attacker can defeat metadata-based checks. No snapshot is a document-content sanitizer.
- Secret Service and SQLite do not share a transaction. Operations are ordered to avoid transmitting bytes before required secret state is durable; safe cleanup is retried for terminal records. An abrupt crash after writing an account/client secret and before its journal association may leave an application-tagged orphan secret, removed by explicit uninstall.
- Google or the browser can complete an action just before the helper is interrupted. Uploaded copies are never automatically deleted. Browser handoff uncertainty is visible and requires explicit reopening.
- A stored, validated link can later become unavailable if the user deletes or moves the document or loses access. Reopen does not query or repair it.
- Support bundles contain versions, counts, fixed event codes, and timestamps. They omit account identity, filenames, paths, document contents, raw logs/databases, and credential values. Inspect an archive before sharing if even aggregate metadata is sensitive.

## Security testing

Fake backends inject secrets into exception text, fail at upload boundaries, forge URLs/metadata, expire authentication, and simulate interrupted writes. Tests inspect serialized QML/RPC state, SQLite/WAL bytes, support archives, subprocess call sites, and helper output. Real-process tests terminate workers at durable boundaries and restart against the same journal and fake remote service. No production endpoint override or plaintext test keyring is exposed by the shipped CLI.
