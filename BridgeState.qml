import QtQuick
import "UiLogic.js" as Logic

Item {
    id: root
    property bool connected: false
    property bool transportReady: false
    signal send(string message)
    property var snapshot: ({ accounts: [], operations: [], authentication: { busy: false, error: null }, settings: {}, setup: { client_configured: false }, active: 0, attention: 0 })
    property var mime: ({ handlers: [], restoration_pending: false })
    property var diagnostics: ({})
    property string error: ""
    property string errorCode: ""
    property string notice: ""
    property var pending: ({})
    signal replied(string method, var result, var params)
    signal failed(string method, var params)

    function isBusy(method, id) {
        for (var key in pending) {
            var item = pending[key]
            if (item.method === method && (id === undefined || item.params.id === id || item.params.key === id)) return true
        }
        return false
    }
    function tell(message) { notice = message; noticeTimer.restart() }
    function dismissError() { error = ""; errorCode = "" }

    function requestId() {
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
            var r = Math.floor(Math.random() * 16)
            return (c === "x" ? r : (r & 3) | 8).toString(16)
        })
    }
    function request(method, params) {
        params = params || {}
        if (!transportReady || !connected) {
            error = "The helper is reconnecting. Try again shortly."
            return false
        }
        var signature = Logic.requestKey(method, params)
        for (var existing in pending) if (pending[existing].signature === signature) return false
        var id = requestId()
        var next = Object.assign({}, pending)
        next[id] = { method: method, params: params, signature: signature }
        pending = next
        if (["mime.status", "diagnostics", "status"].indexOf(method) < 0) { dismissError(); notice = "" }
        send(JSON.stringify({ version: 1, id: id, method: method, params: params }) + "\n")
        return true
    }
    function receive(line) {
        if (line.length > 4194304) return
        try {
            var msg = JSON.parse(line)
            if (msg.version !== 1) return
            if (msg.event === "status" && msg.data && Array.isArray(msg.data.accounts) && Array.isArray(msg.data.operations)) {
                // Preserve list identity while unrelated upload progress changes.
                if (JSON.stringify(msg.data.accounts) === JSON.stringify(snapshot.accounts)) msg.data.accounts = snapshot.accounts
                if (JSON.stringify(msg.data.operations) === JSON.stringify(snapshot.operations)) msg.data.operations = snapshot.operations
                var previousAuth = snapshot.authentication
                snapshot = msg.data
                if (previousAuth.busy && !msg.data.authentication.busy && !msg.data.authentication.error) tell("Google account connected.")
                var wasConnected = connected
                connected = true
                if (!wasConnected) request("mime.status", {})
            } else if (msg.id && pending[msg.id]) {
                var item = pending[msg.id]
                var method = item.method
                var next = Object.assign({}, pending)
                delete next[msg.id]
                pending = next
                if (msg.error) {
                    errorCode = String(msg.error.code || "internal")
                    error = Logic.errorText(errorCode, method)
                    failed(method, item.params)
                }
                else {
                    if (method.indexOf("mime.") === 0) mime = msg.result
                    if (method === "diagnostics") diagnostics = msg.result
                    if (method === "credentials.import") {
                        var updated = Object.assign({}, snapshot)
                        updated.setup = { client_configured: true }
                        snapshot = updated
                    }
                    var messages = { "accounts.rename": "Account name saved.", "accounts.set-default": "Default upload account updated.",
                        "accounts.enable": "Account enabled. Paused uploads will resume.", "accounts.disable": "Account paused.",
                        "accounts.remove": "Account removed. Files in Drive are kept.", "credentials.import": "Custom Google setup saved. You can now connect an account.",
                        "mime.install": "Office files now open with omadocs.", "mime.remove": "Previous file defaults restored where applicable.",
                        "settings.set": "Settings saved.", "activity.assign": "Account selected. Upload queued.",
                        "activity.retry": "Checking and retrying this upload…", "activity.cancel": "Cancellation requested. Any copy already in Drive is kept." }
                    if (messages[method]) tell(messages[method])
                    if (method === "activity.reopen") {
                        if (msg.result.browser === "opened") tell("Opened this Drive copy in your browser.")
                        else {
                            errorCode = "browser"
                            error = "Your copy is uploaded, but the browser could not open. Check your default browser and try again."
                        }
                    }
                    replied(method, msg.result, item.params)
                }
            }
        } catch (_) {
            error = "The helper returned an invalid message."
        }
    }
    Timer {
        id: noticeTimer
        interval: 5500
        onTriggered: root.notice = ""
    }
}
