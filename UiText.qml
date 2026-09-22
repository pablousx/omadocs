import QtQuick
import qs.Commons

Text {
    readonly property var themeFont: Style.font
    property bool secondary: false
    property bool section: false
    textFormat: Text.PlainText
    color: Color.foreground
    opacity: secondary ? 0.70 : 1
    font.family: themeFont.family
    font.pixelSize: section ? themeFont.caption : Style.space(secondary ? 11 : 12)
    font.bold: section
    font.capitalization: section ? Font.AllUppercase : Font.MixedCase
    font.letterSpacing: section ? 1 : 0
    wrapMode: Text.Wrap
    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
