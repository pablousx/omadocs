import QtQuick
Rectangle {
    property color foreground: "#eeeeee"
    property real strength: 0.12
    height: 1
    color: Qt.rgba(foreground.r, foreground.g, foreground.b, strength)
}
