import QtQuick
import Quickshell.Io

Item {
    id: root
    required property string helper
    property string kind: "files"
    property bool busy: false
    property bool received: false
    property bool shuttingDown: false
    signal selected(var files)
    signal cancelled()
    signal failed(string message)

    function open(mode) {
        if (busy || process.running) return
        kind = mode
        received = false
        busy = true
        process.running = true
    }
    function receive(line) {
        received = true
        busy = false
        try {
            if (line.length > 4194304) throw new Error("size")
            var result = JSON.parse(line)
            if (result.cancelled) cancelled()
            else if (result.error) failed(String(result.error.message))
            else if (Array.isArray(result.files)) selected(result.files)
            else throw new Error("shape")
        } catch (_) {
            failed("The file picker returned an invalid selection. Try again.")
        }
    }
    Process {
        id: process
        command: ["/usr/bin/python", "-I", root.helper, "_pick", root.kind]
        running: false
        stdout: StdioCollector { onStreamFinished: { if (typeof root.receive === "function" && !root.shuttingDown) root.receive(text) } }
        onRunningChanged: if (!running && root.busy && !root.shuttingDown) settled.restart()
        // Quickshell 0.3.1 omits QProcess::ExitStatus from its qmltypes. This
        // handler uses no signal parameters; the runtime signal is supported.
        // qmllint disable signal-handler-parameters
        onExited: if (!root.shuttingDown) settled.restart()
        // qmllint enable signal-handler-parameters
    }
    Timer {
        id: settled
        interval: 50
        onTriggered: {
            root.busy = false
            if (!root.received) root.failed("The file picker could not start. You can still use Open with → omadocs in your file manager.")
        }
    }
    Component.onDestruction: { shuttingDown = true; settled.stop(); process.running = false }
}
