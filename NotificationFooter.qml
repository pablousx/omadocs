import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import qs.Commons

Item {
    id: root
    property string message: ""
    property bool error: false
    property bool dismissible: false
    property bool setupAvailable: false
    signal dismissed()
    signal setupRequested()

    // Reserve two text lines and the action height even while empty.
    implicitHeight: Math.ceil(Math.max(metrics.height * 2, dismiss.implicitHeight, setup.implicitHeight)) + Style.space(18)
    Rectangle {
        anchors.fill: parent
        visible: root.message !== ""
        radius: Style.space(6)
        color: Qt.alpha(root.error ? Color.urgent : Color.accent, 0.07)
        border.color: Qt.alpha(root.error ? Color.urgent : Color.accent, 0.16)
    }
    FontMetrics { id: metrics; font: label.font }
    RowLayout {
        anchors.fill: parent
        anchors.margins: Style.space(9)
        spacing: Style.space(6)
        UiText {
            id: label
            objectName: "notification-message"
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: root.message
            color: root.error ? Color.urgent : Color.foreground
            secondary: true
            maximumLineCount: 2
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            HoverHandler { id: hover }
            QQC.ToolTip {
                objectName: "notification-tooltip"
                visible: hover.hovered && label.truncated
                delay: 400
                width: Math.min(root.width, Style.space(520))
                text: root.message
                contentItem: UiText { text: root.message }
                background: Rectangle { color: Color.background; border.color: Color.foreground }
            }
        }
        UiAction {
            id: setup
            text: "Custom Google setup"
            link: true
            visible: root.setupAvailable
            onClicked: root.setupRequested()
        }
        UiAction {
            id: dismiss
            text: "Dismiss"
            link: true
            visible: root.dismissible
            onClicked: root.dismissed()
        }
    }
}
