import QtQuick
import QtQuick.Controls as QQC
QQC.Button {
    property bool focusable: true
    property bool bordered: false
    property bool selected: false
    property bool leftAlign: false
    property string tooltipText: ""
    property string iconText: ""
    property bool iconSpinning: false
    property color foreground: "#eeeeee"
    activeFocusOnTab: focusable
}
