# Uninstall

Removing the plugin's source before restoring MIME associations can leave a broken handler. Use this order:

1. Cancel or finish pending uploads. An already completed Google copy is never deleted by omadocs.
2. Run `omadocs uninstall` (or `./omadocs-run uninstall` from this checkout). It disables the plugin in the existing shell, restores previous MIME defaults conditionally, removes unchanged generated launchers/desktop entries, erases application-tagged Secret Service items, and clears omadocs's operation/account/settings history and snapshots. If it reports Busy or a keyring/MIME error, resolve that and retry before deleting source.
3. Remove the installed plugin using `omarchy plugin remove io.github.pablousx.omadocs`. Follow Omarchy's own confirmation prompt. The development checkout is not removed by omadocs.

To restore only file handlers while keeping accounts and history:

```bash
./omadocs-run mime remove
```

Restoration only applies while omadocs is still the active handler. A default chosen later is preserved. Generated files modified by the user are also preserved rather than deleted. Previously unset defaults return to absence/fallback behavior.

Disabling the widget alone does not erase accounts or stop admitted uploads. After uninstall, the idle helper exits; empty private state/cache/runtime directories and its empty journal may remain. Do not delete unrelated state files belonging to another tool or an older implementation. The helper does not read or migrate arbitrary databases found beside its own `journal.sqlite3`.

Google files remain in Drive. Removing local credentials does not necessarily revoke Google's authorization grant; revoke access separately in Google Account → Security → connections to third-party apps if desired. The original advanced credential-import file also remains under your control and is never deleted by omadocs.
