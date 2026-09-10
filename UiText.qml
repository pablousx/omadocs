import QtQuick
import qs.Commons

Text {
    readonly property var themeFont: Style.font
    property bool secondary: false
    textFormat: Text.PlainText
    color: Color.foreground
    opacity: secondary ? 0.75 : 1
    font.family: themeFont.family
    font.pixelSize: secondary ? themeFont.caption : themeFont.body
    wrapMode: Text.Wrap
    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
