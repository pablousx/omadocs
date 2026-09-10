import QtQuick
import Quickshell.Io

BridgeState {
    id: root
    property bool shuttingDown: false
    readonly property string helper: decodeURIComponent(String(Qt.resolvedUrl("omadocs-run")).replace(/^file:\/\//, ""))
    transportReady: process.running
    onSend: message => process.write(message)
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
