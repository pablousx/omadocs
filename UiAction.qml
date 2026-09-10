import QtQuick
import qs.Commons
import qs.Ui as UI

UI.Button {
    id: root
    property bool busy: false
    property bool available: true
    property bool primary: false
    property bool destructive: false
    readonly property var parentItem: parent
    // Qt already skips hidden/disabled items in Tab traversal. Toggling
    // activeFocusOnTab while this button has focus produces a Qt warning.
    focusable: true
    bordered: primary
    selected: primary
    enabled: available && !busy
    opacity: enabled || busy ? 1 : 0.4
    foreground: destructive ? Color.urgent : Color.foreground
    iconText: busy ? "\uf110" : ""
    iconSpinning: busy
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.description: tooltipText
    Accessible.onPressAction: if (enabled) clicked()
    onActiveFocusChanged: if (activeFocus) {
        var ancestor = parentItem
        while (ancestor) {
            if (typeof ancestor.reveal === "function") { ancestor.reveal(root); break }
            ancestor = ancestor.parent
        }
    }
}
