import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool connected: false
    property bool shuttingDown: false
    property var snapshot: ({ accounts: [], operations: [], authentication: { busy: false, error: null }, settings: {}, active: 0, attention: 0 })
    property var mime: ({ handlers: [], restoration_pending: false })
    property var diagnostics: ({})
    property string error: ""
    property var pending: ({})
    readonly property string helper: decodeURIComponent(String(Qt.resolvedUrl("omadocs-run")).replace(/^file:\/\//, ""))
    signal replied(string method, var result)

    function requestId() {
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
            var r = Math.floor(Math.random() * 16)
            return (c === "x" ? r : (r & 3) | 8).toString(16)
        })
    }
    function request(method, params) {
        if (!process.running || !connected) {
            error = "The helper is reconnecting. Try again shortly."
            return
        }
        var id = requestId()
        var next = Object.assign({}, pending)
        next[id] = method
        pending = next
        error = ""
        process.write(JSON.stringify({ version: 1, id: id, method: method, params: params || {} }) + "\n")
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
                snapshot = msg.data
                var wasConnected = connected
                connected = true
                if (!wasConnected) request("mime.status", {})
            } else if (msg.id && pending[msg.id]) {
                var method = pending[msg.id]
                var next = Object.assign({}, pending)
                delete next[msg.id]
                pending = next
                if (msg.error) error = String(msg.error.message || "Action failed.")
                else {
                    if (method.indexOf("mime.") === 0) mime = msg.result
                    if (method === "diagnostics") diagnostics = msg.result
                    replied(method, msg.result)
                }
            }
        } catch (_) {
            error = "The helper returned an invalid message."
        }
    }
    Process {
        id: process
        command: ["/usr/bin/python", "-I", root.helper, "_bridge"]
        stdinEnabled: true
        running: false
        stdout: SplitParser {
            // A final pipe notification may arrive while Qt tears down a
            // component during plugin reload and removes its JS methods.
            onRead: data => {
                if (typeof root.receive === "function" && !root.shuttingDown) root.receive(data)
            }
        }
        // No raw helper stderr or OAuth data is forwarded into the shell logs.
        onRunningChanged: if (!running && !root.shuttingDown) {
            root.connected = false
            root.pending = ({})
            reconnect.restart()
        }
    }
    Component.onCompleted: process.running = true
    Component.onDestruction: {
        shuttingDown = true
        reconnect.stop()
        process.running = false
    }
    Timer {
        id: reconnect
        interval: 2500
        onTriggered: process.running = true
    }
}
