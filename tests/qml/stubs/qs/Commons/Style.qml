pragma Singleton
import QtQuick
QtObject {
    function space(value) { return value }
    readonly property int cornerRadius: 4
    readonly property var font: ({family: "sans-serif", body: 14, caption: 12, subtitle: 17, icon: 16})
}
