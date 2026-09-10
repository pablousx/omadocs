import QtQuick
import qs.Ui as UI

UI.BarWidget {
    id: root
    moduleName: "io.github.pablousx.omadocs"
    readonly property bool opened: panel.opened
    readonly property bool popoutSwitchClosing: panel.popoutSwitchClosing
    readonly property bool authAttention: !!backend.snapshot.authentication.error && !(backend.snapshot.authentication.error === "credentials_required" && backend.snapshot.setup && backend.snapshot.setup.client_configured)
    function open() { panel.open() }
    function close() { panel.close() }
    function toggle() { panel.toggle() }
    function closeForPopoutSwitch() { panel.closeForPopoutSwitch() }
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    Bridge { id: backend }
    UI.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: backend.snapshot.active > 0 ? "\uf15c " + backend.snapshot.active : (backend.snapshot.attention > 0 || root.authAttention ? "\uf15c ·" : "\uf15c")
        opacity: backend.snapshot.active > 0 || backend.snapshot.attention > 0 || root.authAttention || backend.snapshot.authentication.busy ? 1 : 0.65
        tooltipText: !backend.connected ? "omadocs · reconnecting…"
            : backend.snapshot.authentication.busy ? "omadocs · finish Google sign-in in your browser"
            : root.authAttention ? "omadocs · Google sign-in needs attention"
            : backend.snapshot.attention > 0 ? "omadocs · " + backend.snapshot.attention + " upload(s) need attention"
            : backend.snapshot.active > 0 ? "omadocs · " + backend.snapshot.active + " upload(s) in progress"
            : "omadocs · upload Office files to Google Drive"
        onPressed: function(buttonCode) { if (buttonCode === Qt.LeftButton) root.toggle() }
    }
    Panel {
        id: panel
        bar: root.bar
        anchorItem: button
        hostWidget: root
        bridge: backend
    }
}
