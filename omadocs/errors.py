"""Only fixed, audited messages cross the helper boundary."""
MESSAGES = {
    "invalid_input": "Invalid input. Supply a supported local Office file or a valid command.",
    "local_file": "Cannot read a stable, regular Office file. Check access, format, and available disk space.",
    "source_changed": "The source changed while being copied. Save it and open it again.",
    "snapshot_missing": "The temporary upload copy is unavailable. This operation cannot upload again.",
    "authentication": "Authentication is required for this upload account.",
    "account_mismatch": "The signed-in Google account does not match the account being reauthenticated.",
    "account_disabled": "This account is disabled. Enable it to continue.",
    "account_required": "Choose an enabled upload account in the omadocs panel.",
    "credentials_required": "The production Desktop OAuth client is not configured. Import Desktop credentials for development.",
    "keyring": "Secret Service is unavailable or locked. Unlock your login keyring and retry.",
    "offline": "Google could not be reached. Check your connection and retry this operation.",
    "quota": "Google reports a quota or rate limit. Retry later or check Drive storage.",
    "permission": "Google refused this operation. Check account or organization permissions.",
    "invalid_response": "Google returned an unexpected response. The browser was not opened.",
    "browser": "The upload succeeded, but the browser could not be opened. Use Reopen.",
    "auth_browser": "The default browser could not open Google authorization.",
    "auth_cancelled": "Google authorization was cancelled or timed out.",
    "busy": "The operation is busy. Try again shortly.",
    "cancelled": "The upload was cancelled. An already completed Drive copy is not deleted.",
    "not_found": "The requested account or activity is no longer available.",
    "mime": "MIME setup could not be completed. Check diagnostics and retry removal to restore associations.",
    "dependency": "A required system dependency is missing. See the development guide.",
    "internal": "The helper could not complete this action. See redacted diagnostics.",
    "ipc": "The local helper is unavailable or the IPC message is invalid.",
}

class Fault(Exception):
    def __init__(self, code, *, retryable=False, retry_after=0):
        self.code = code if code in MESSAGES else "internal"
        self.retryable = retryable
        self.retry_after = min(max(float(retry_after), 0), 60)
        super().__init__(MESSAGES[self.code])

    def public(self):
        return {"code": self.code, "message": MESSAGES[self.code]}
