import QtQuick
import QtQuick.Controls as QQC
Column {
    id: root
    property string label: ""
    property int from: 0
    property int to: 100
    property int value: 0
    signal modified(int value)
    QQC.Label { text: root.label }
    QQC.SpinBox { from: root.from; to: root.to; value: root.value; onValueModified: root.modified(value) }
}
