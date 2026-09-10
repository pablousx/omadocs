import QtQuick
import qs.Commons
import QtQuick.Controls as QQC

QQC.Button {
    id: root
    readonly property var themeFont: Style.font
    property bool busy: false
    property bool available: true
    property bool primary: false
    property bool destructive: false
    readonly property var parentItem: parent
    // Qt already skips hidden/disabled items in Tab traversal. Toggling
    // activeFocusOnTab while this button has focus produces a Qt warning.
    property bool selected: primary
    property bool leftAlign: false
    property bool link: false
    property string tooltipText: ""
    readonly property color tint: destructive ? Color.urgent : primary || selected || link ? Color.accent : Color.foreground
    implicitHeight: Math.max(Style.space(38), label.implicitHeight + Style.space(18))
    implicitWidth: Math.max(Style.space(link ? 0 : 80), label.implicitWidth + Style.space(24))
    padding: Style.space(12)
    activeFocusOnTab: true
    hoverEnabled: true
    QQC.ToolTip.visible: hovered && tooltipText !== ""
    QQC.ToolTip.text: tooltipText
    QQC.ToolTip.delay: 700
    contentItem: Text {
        id: label
        text: (root.busy ? "◌ " : "") + root.text
        textFormat: Text.PlainText
        color: root.tint
        horizontalAlignment: root.leftAlign ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: root.themeFont.family
        font.pixelSize: Style.space(12)
        font.underline: root.link && root.hovered
        wrapMode: Text.WordWrap
    }
    background: Rectangle {
        radius: Style.space(6)
        color: Qt.alpha(root.tint, root.down ? 0.22 : root.hovered ? 0.14 : root.primary || root.selected ? 0.10 : root.link ? 0 : 0.045)
        border.color: root.activeFocus ? Color.accent : Qt.alpha(root.tint, root.primary || root.selected ? 0.45 : root.link ? 0 : 0.15)
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
    enabled: available && !busy
    opacity: enabled || busy ? 1 : 0.4
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
