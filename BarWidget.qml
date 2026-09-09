import QtQuick
import qs.Ui as UI

UI.BarWidget {
    id: root
    moduleName: "io.github.pablousx.omadocs"
    readonly property bool opened: panel.opened
    readonly property bool popoutSwitchClosing: panel.popoutSwitchClosing
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
        text: backend.snapshot.active > 0 ? "\uf15c " + backend.snapshot.active : (backend.snapshot.attention > 0 ? "\uf15c ·" : "\uf15c")
        opacity: backend.snapshot.active > 0 || backend.snapshot.attention > 0 ? 1 : 0.65
        tooltipText: backend.connected ? "omadocs · upload a new Drive copy" : "omadocs · helper reconnecting"
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
