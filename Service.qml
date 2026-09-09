import QtQuick

Item {
    // Keeps a local status subscription while enabled. The external helper owns
    // uploads and credentials and survives this item's destruction/hot reload.
    property var shell: null
    Bridge { }
}
