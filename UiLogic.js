// Presentation only. No file access, network, credentials, or state mutations.
function needsAttention(job) {
    return ["failed", "auth_required", "waiting_account", "paused", "unresolved"].indexOf(job.state) >= 0
        || job.state === "complete" && ["failed", "uncertain"].indexOf(job.browser) >= 0;
}

function progress(job) {
    return job.size > 0 ? Math.max(0, Math.min(1, job.progress / job.size)) : 0;
}

function stateLabel(job) {
    if (job.state === "complete") {
        if (job.browser === "launching" || job.browser === "pending") return "Uploaded · opening browser…";
        if (job.browser === "failed") return "Uploaded · browser could not open";
        if (job.browser === "uncertain") return "Uploaded · check your browser";
        return "Uploaded";
    }
    var labels = { preparing: "Preparing a private copy…", ready: "Queued", uploading: "Uploading",
        waiting_account: "Choose an upload account", auth_required: "Sign-in needed", paused: "Account paused",
        failed: "Needs attention", cancelled: "Cancelled", expired: "Temporary copy expired", unresolved: "Check upload outcome" };
    return labels[job.state] || "Waiting";
}

function errorText(code, method) {
    if (method === "credentials.import" && ["invalid_input", "local_file"].indexOf(code) >= 0)
        return "Choose a readable Google OAuth JSON for a Desktop app. Web and service-account credentials are not supported.";
    if (method === "accounts.rename" && code === "invalid_input")
        return "Use an account name of 1–80 characters, without line breaks.";
    var messages = {
        authentication: "Sign in again to resume this account’s uploads.",
        account_mismatch: "Sign in with this account’s original Google email. To use another email, add an account.",
        keyring: "Unlock your login keyring, then try again.",
        credentials_required: "Google sign-in needs a one-time app setup. Import a Desktop OAuth JSON in Settings → Custom Google setup.",
        offline: "Connection interrupted. Check your internet connection, then retry.",
        quota: "Google reports a storage or rate limit. Check Drive storage or retry later.",
        permission: "Google refused access. Check this account’s permissions or ask your organization’s administrator.",
        local_file: "The file could not be prepared. Check its format, access permissions, and free disk space, then choose it again.",
        source_changed: "The file changed while being copied. Save your changes, then choose it again.",
        snapshot_missing: "The temporary copy is gone. An uncertain upload can only be checked in Drive; it will not upload again.",
        invalid_response: "Google returned an unexpected response. Retry to check the existing upload safely.",
        auth_cancelled: "Google sign-in was cancelled or timed out. You can try again.",
        auth_browser: "Google sign-in could not open. Check your default browser, then try again.",
        account_disabled: "This account is paused. Enable it to resume uploads.",
        cancelled: "Cancelled. A copy already received by Google remains in Drive.",
        busy: "Another action is still finishing. Wait a moment and try again.",
        not_found: "This item is no longer available. The activity list will refresh.",
        mime: "File defaults could not be updated. Check Settings → Diagnostics before trying again.",
        invalid_input: "Check the input. Choose local DOCX, XLSX, or PPTX files, up to 64 at a time.",
        ipc: "The helper is reconnecting. Your existing uploads are kept.",
        internal: "The action could not finish. Check Settings → Diagnostics."
    };
    return messages[code] || "The action could not finish. Try again or check Diagnostics.";
}

function fileSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return Math.ceil(bytes / 1024) + " KB";
    return (bytes / 1048576).toFixed(bytes < 10485760 ? 1 : 0) + " MB";
}

function relativeTime(seconds, now) {
    var age = Math.max(0, now / 1000 - seconds);
    if (age < 60) return "Just now";
    if (age < 3600) return Math.floor(age / 60) + " min ago";
    if (age < 86400) return Math.floor(age / 3600) + " hr ago";
    return Math.floor(age / 86400) + " d ago";
}

function visibleJobs(jobs, filter, limit) {
    return jobs.filter(function(job) {
        return filter === "attention" ? needsAttention(job) : filter === "complete" ? job.state === "complete" : true;
    }).sort(function(a, b) { return b.created - a.created || a.id.localeCompare(b.id); }).slice(0, limit);
}

// Update existing roles in place so upload progress cannot destroy a focused
// delegate, reset a confirmation, or jump the scroll position.
function syncRows(model, rows) {
    for (var i = 0; i < rows.length; i++) {
        var key = rows[i].id;
        if (i >= model.count || model.get(i).key !== key) {
            var found = -1;
            for (var j = i + 1; j < model.count; j++) if (model.get(j).key === key) { found = j; break; }
            if (found >= 0) model.move(found, i, 1);
            else model.insert(i, { key: key, record: rows[i], serialized: JSON.stringify(rows[i]) });
        }
        var serialized = JSON.stringify(rows[i]);
        if (model.get(i).serialized !== serialized) {
            model.setProperty(i, "record", rows[i]);
            model.setProperty(i, "serialized", serialized);
        }
    }
    if (model.count > rows.length) model.remove(rows.length, model.count - rows.length);
}

function requestKey(method, params) {
    return method + ":" + (params.id || params.key || "");
}

function handlerName(id) {
    if (!id) return "System default";
    if (id.indexOf("onlyoffice") >= 0) return "OnlyOffice";
    if (id.indexOf("libreoffice-writer") >= 0) return "LibreOffice Writer";
    if (id.indexOf("libreoffice-calc") >= 0) return "LibreOffice Calc";
    if (id.indexOf("libreoffice-impress") >= 0) return "LibreOffice Impress";
    return id.replace(/\.desktop$/, "").replace(/[._-]+/g, " ");
}
