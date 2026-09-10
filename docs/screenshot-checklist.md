# Screenshot checklist

Capture only the plugin surface on a neutral desktop. Use fake accounts and disposable fake filenames; never expose real account emails, private document titles, credentials, callback URLs, logs, or unrelated application content. Keep unredacted desktop captures outside the repository and support bundles.

- [ ] Quiet idle bar icon in the active Omarchy theme.
- [ ] Accounts: two fictitious accounts, local labels, one default, one disabled.
- [ ] Uploads: streaming progress, owner label, an authentication error, completed upload, and Open in browser.
- [ ] Browser failure/uncertainty clearly separate from upload success.
- [ ] Account picker for a waiting multi-file batch.
- [ ] Google setup and authentication feedback: idle, awaiting browser consent, missing client, and locked keyring states, without secrets.
- [ ] Settings → File opening: original defaults, omadocs installed, and previous defaults restored.
- [ ] Settings: account-choice toggle, collapsed setup/history/diagnostics, and expanded retention controls.
- [ ] Redacted diagnostics containing only counts, versions, timestamps, and fixed event codes.
- [ ] Keyboard focus, Escape dismissal, narrow/vertical bar, multiple monitors, long Unicode names, and light/dark themes.
- [ ] Live Office landing behavior only after live credentials are provided; describe the observation without recording browser auth details.

During local development, capture after the panel animation finishes. Some Omarchy screenshot workflows dismiss panels; a direct local `grim` capture can preserve the open panel. Do not publish captures containing unrelated desktop content.
