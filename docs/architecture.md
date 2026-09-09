# Architecture

## Boundaries

The Quattro manifest loads a small service and a bar widget. `BarWidget.qml` hosts the theme-aware panel; each UI connection uses `Bridge.qml` to send validated, non-secret JSON to a Python bridge process. The service maintains a local subscription while enabled. All bridges connect to one helper; multiple monitors never create independent upload engines.

The helper starts on demand under a process lock and exposes a mode-0600 Unix socket inside a mode-0700 runtime directory. It checks peer UID, protocol version, UUID request IDs, method/parameter allowlists, types, and message size. The QML bridge never receives Google token responses, OAuth callback URLs, resumable URLs, or arbitrary exception messages. It receives account labels/email, upload progress, safe error codes, and allowlisted diagnostics.

The CLI uses the same dispatcher as the panel. It passes file paths as JSON, not shell text. Browser/desktop/shell commands use explicit argument arrays. `xdg-open` receives only an authorization-request URL (without a code/token) or a validated returned Google view link. OAuth callback handling and token exchange occur exclusively in the helper.

## Upload data flow

1. Validate all request structure and local URI syntax. Resolve relative CLI paths before IPC.
2. Assign each input an operation UUID derived from the invocation UUID and its position. A repeated IPC request finds the same operations; a new user invocation gets new UUIDs.
3. Journal `preparing`, open the source by descriptor without following symlinks, and create a private stable snapshot. Validate OOXML metadata and calculate the binary MD5 checksum expected from Drive.
4. Persist the selected account and owner, then queue `ready`; without an account use `waiting_account`. A later default change never retargets admitted work.
5. Obtain an unused Drive ID, commit it, and initiate a resumable upload with that ID and an application-private operation marker. Persist its session URI in Secret Service before transmitting bytes.
6. Probe the committed offset and stream chunks. After an uncertain write, probe before resending. After session expiry, reconcile the owned ID and reuse it for a replacement session if necessary.
7. Verify returned metadata against the persisted ID, operation marker, MIME, size, checksum, and owner. The browser link must name that same file on a supported Google host.
8. Commit `complete`, remove the temporary copy/session secret, then record the browser handoff. Browser failure never changes upload success into upload failure.

The Google adapter implements only the required token exchange/refresh, `about.get`, `files.generateIds`, `files.create` resumable initiation, resumable upload/status requests, and metadata `files.get` for a known operation ID. There is no file listing, change feed, download, folder routing, revision API, or source-to-remote mapping table.

## Durable state and crash boundaries

SQLite uses WAL and `synchronous=FULL`. Account metadata, settings, MIME backups, safe event codes, and operations are its entire scope. Document bytes stay in private snapshot files; authorization codes and PKCE verifiers stay in memory. Secrets are written through Secret Service only.

| State | Meaning / recovery |
| --- | --- |
| `preparing` | Snapshot admission is incomplete; a crash becomes a local-file failure and cleans partial bytes. |
| `waiting_account` | Stable temporary bytes exist; selection is required before any Google upload. |
| `ready`, `uploading` | Recover using the original owned Drive ID and stored session; reconcile remote completion before requiring local bytes. |
| `auth_required`, `paused` | Keep the original operation; reauthenticate/unlock/enable before resuming. |
| `failed` | Show a fixed error code. Retry preserves the original Drive ID. |
| `unresolved` | Local bytes are unavailable but the original Drive ID is retained. Retry only reconciles that ID; Cancel explicitly abandons it. |
| `complete` | Upload confirmed. Reopen never uploads. |
| `cancelled`, `expired` | No more uploads from this operation; clean temporary data. Drive copies are never deleted. |

The dangerous ambiguity is a final PUT accepted by Google followed by a lost response. A pre-generated file ID and operation marker allow metadata reconciliation; another create with the same ID cannot create a second file. An unused generated ID lost before its local commit is harmless because no file creation has begun.

Exactly-once browser display cannot be guaranteed across process death. The journal records intent before launch, and an interrupted handoff becomes `uncertain`; the user explicitly reopens it. Reopening may open another browser tab, never another Drive file.

## Concurrency and lifecycle

Snapshot admission is serialized to coordinate request receipts and account removal. Three workers stream uploads; account token refreshes are serialized independently. OAuth authorization runs in one separate worker so callbacks do not block status or active uploads. Account choices, reauthentication identity, and original operation IDs remain fixed across retries.

The helper outlives QML reloads. Local subscriptions receive events rather than polling Google. Without clients or runnable work it exits after an idle interval. Compatible helper updates use a code fingerprint and request idle shutdown; running uploads retain the old helper until they finish.

## MIME restoration

Installation backs up the exact target MIME entries and effective defaults before creating the desktop entry. It writes the current desktop's user-level `mimeapps.list`, using atomic replacement and preserving unrelated lines. The executable launcher is separate from the desktop file so paths can be safely quoted.

Removal restores prior entries only while omadocs is still effective. If another default has taken priority, it removes only a stale omadocs association without restoring over that choice. Originally absent entries return to absence. Generated files are removed only if their content still matches the recorded hash; user-modified files are preserved. Durable backups survive incomplete removal.
