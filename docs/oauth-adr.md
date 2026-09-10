# ADR 001: Desktop OAuth, minimal Drive scope, Secret Service

Status: accepted for version 0.1.0. The maintainer approved bundling both Desktop application fields; packaged-client refresh passed. Clean-user consent and full Office browser validation remain unverified.

## Decision

Use the maintainer's Google OAuth **Desktop app** client for normal releases. Request only `https://www.googleapis.com/auth/drive.file`. Use an external default browser, authorization code flow, S256 PKCE, cryptographic state, and an ephemeral HTTP callback bound exclusively to `127.0.0.1`. Never use embedded browsers, out-of-band copy/paste codes, a hosted token relay, service-account ownership, or browser automation.

Google's current [installed-application documentation](https://developers.google.com/identity/protocols/oauth2/native-app) supports loopback redirects for Desktop clients, recommends PKCE, and describes the token exchange. The implementation uses a random callback path, validates state and Host, accepts a bounded single-use callback, sends no reflected code in its response, and closes the listener after completion or timeout. Redirect responses are never automatically followed by the authenticated HTTP client.

Access/refresh tokens and resumable session URLs are stored only in Secret Service. Codes and PKCE verifiers are memory-only. An unavailable/locked keyring prevents authentication or upload; there is no plaintext, environment-variable, or SQLite fallback. Imported client configuration, including any client secret, also stays in Secret Service. The original import file remains user-managed.

Account identity comes from `about.get(fields=user(...))`, which accepts `drive.file`. This avoids additional identity scopes. A renamed label does not become an identity assertion; reauthentication must match the original Google permission ID.

## Maintainer production flow

1. Create a maintainer-owned Google Cloud project and enable Drive API.
2. Configure an external OAuth consent screen, accurate branding, support contact, privacy policy, and terms as applicable. Request only `drive.file`.
3. Create a Desktop OAuth client. Set the publishing status appropriately for production and complete the Google branding/verification requirements actually shown for that project. `drive.file` is documented as a recommended, non-sensitive scope; that does not excuse consent/branding requirements.
4. Validate the exact Desktop client. On September 9, 2026, live refresh using only the client ID failed with `invalid_request`; the otherwise identical request with the Desktop `client_secret` succeeded. The release therefore bundles both fields, with the maintainer's explicit approval.
5. Ship `assets/oauth-client.json` containing only `client_id` and `client_secret`. The loader bounds the file and field sizes and rejects other keys. Do not bundle Google's downloaded credential document, user tokens, authorization codes, or service-account keys. Imported custom client configuration still takes precedence for new accounts; existing accounts retain their client association.
6. Verify a clean release installation can add an account without a user-created Cloud project. Refresh with the exact packaged configuration passed, but a fresh user's browser consent has not been independently verified; do not represent it as tested.

Desktop clients are public clients. A distributed Desktop `client_secret` cannot prove that a caller is the official app and must not be treated as a confidential server credential. PKCE binds an authorization response to its initiating helper; it does not prevent another application from reusing the public client configuration. User access/refresh tokens remain private and are never included in the release. See [RFC 8252, section 8.5](https://www.rfc-editor.org/rfc/rfc8252#section-8.5).

All installations share the application project's API quota. Reuse can cause throttling and affect the application's reputation. Standard Drive API use is currently free; Google has announced paid usage above standard thresholds later in 2026, with notice. Keep the project dedicated to omadocs, monitor usage and policy changes, and review billing before opting into paid quota increases. Publication does not enable or change Cloud billing. The project's actual billing linkage has not been verified. See [Drive limits](https://developers.google.com/workspace/drive/api/guides/limits) and [Google's announced model](https://developers.google.com/workspace/tools-safety).

Google documents [seven-day refresh-token expiry for external projects in Testing](https://developers.google.com/identity/protocols/oauth2#expiration) when scopes go beyond the basic identity exceptions. That applies to Drive development tests and must not be mistaken for a stable production configuration.

## Advanced custom clients

`omadocs credentials import /absolute/path/to/client.json` accepts Google's `installed` object with a Desktop client ID, validates Google's authorization/token endpoints, rejects Web credentials and embedded user tokens, and saves the imported configuration in Secret Service. A custom client becomes the default for newly added accounts only. Existing accounts keep their original client for refresh and reauthentication.

Use a dedicated Desktop client for forks/development. A reused client with previously granted broader scopes may return a broader grant; omadocs rejects such a response rather than widening its access. Do not paste credentials into chat or issue reports.

## Consequences

There is no server to maintain or token custody outside the local user session. Users authorize file creation through Google's UI. Account removal erases local credentials and cancels pending work; it does not delete documents or automatically revoke a potentially shared Google authorization grant. Users can revoke access separately in their Google Account settings.

A browser's active account remains independent of the account used by the upload API. The returned link is opened unchanged and ownership is displayed in omadocs. Any required Google “Open with” step must be observed live and documented; it cannot be inferred solely from upload success.

References: [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [loopback migration](https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration), [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [about.get authorization](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get), [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies).
