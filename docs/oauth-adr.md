# ADR 001: Desktop OAuth, minimal Drive scope, Secret Service

Status: accepted for implementation; maintainer client provisioning and live validation pending.

## Decision

Use the maintainer's Google OAuth **Desktop app** client for normal releases. Request only `https://www.googleapis.com/auth/drive.file`. Use an external default browser, authorization code flow, S256 PKCE, cryptographic state, and an ephemeral HTTP callback bound exclusively to `127.0.0.1`. Never use embedded browsers, out-of-band copy/paste codes, a hosted token relay, service-account ownership, or browser automation.

Google's current [installed-application documentation](https://developers.google.com/identity/protocols/oauth2/native-app) supports loopback redirects for Desktop clients, recommends PKCE, and describes the token exchange. The implementation uses a random callback path, validates state and Host, accepts a bounded single-use callback, sends no reflected code in its response, and closes the listener after completion or timeout. Redirect responses are never automatically followed by the authenticated HTTP client.

Access/refresh tokens and resumable session URLs are stored only in Secret Service. Codes and PKCE verifiers are memory-only. An unavailable/locked keyring prevents authentication or upload; there is no plaintext, environment-variable, or SQLite fallback. Imported client configuration, including any client secret, also stays in Secret Service. The original import file remains user-managed.

Account identity comes from `about.get(fields=user(...))`, which accepts `drive.file`. This avoids additional identity scopes. A renamed label does not become an identity assertion; reauthentication must match the original Google permission ID.

## Maintainer production flow

1. Create a maintainer-owned Google Cloud project and enable Drive API.
2. Configure an external OAuth consent screen, accurate branding, support contact, privacy policy, and terms as applicable. Request only `drive.file`.
3. Create a Desktop OAuth client. Set the publishing status appropriately for production and complete the Google branding/verification requirements actually shown for that project. `drive.file` is documented as a recommended, non-sensitive scope; that does not excuse consent/branding requirements.
4. Validate OAuth using the maintained Desktop client, including refresh and multiple accounts. Google lists `client_secret` as optional for the current installed-app token exchange; **verify this with the actual production client before shipping the public-client-only configuration**. Do not silently substitute another flow if that client fails.
5. Bundle only the validated public client ID as `assets/oauth-client.json` with this shape:

   ```json
   {"client_id": "THE_MAINTAINER_DESKTOP_CLIENT_ID.apps.googleusercontent.com"}
   ```

   The example above is illustrative, not a usable client ID. No placeholder file is shipped as if configured. The real value must match Google's Desktop client format. The helper stores its client association in Secret Service before account creation.
6. Verify a clean release installation can add an account without a user-created Cloud project. Until this passes, the production flow remains a release gate.

Desktop clients are public clients; a client ID is not an authentication secret. PKCE binds the authorization response to the initiating helper. Keeping user tokens out of QML and subprocesses is a separate, stronger requirement.

Google documents [seven-day refresh-token expiry for external projects in Testing](https://developers.google.com/identity/protocols/oauth2#expiration) when scopes go beyond the basic identity exceptions. That applies to Drive development tests and must not be mistaken for a stable production configuration.

## Advanced custom clients

`omadocs credentials import /absolute/path/to/client.json` accepts Google's `installed` object with a Desktop client ID, validates Google's authorization/token endpoints, rejects Web credentials and embedded user tokens, and saves the imported configuration in Secret Service. A custom client becomes the default for newly added accounts only. Existing accounts keep their original client for refresh and reauthentication.

Use a dedicated Desktop client for forks/development. A reused client with previously granted broader scopes may return a broader grant; omadocs rejects such a response rather than widening its access. Do not paste credentials into chat or issue reports.

## Consequences

There is no server to maintain or token custody outside the local user session. Users authorize file creation through Google's UI. Account removal erases local credentials and cancels pending work; it does not delete documents or automatically revoke a potentially shared Google authorization grant. Users can revoke access separately in their Google Account settings.

A browser's active account remains independent of the account used by the upload API. The returned link is opened unchanged and ownership is displayed in omadocs. Any required Google “Open with” step must be observed live and documented; it cannot be inferred solely from upload success.

References: [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [loopback migration](https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration), [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [about.get authorization](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get), [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies).
