pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import qs.Commons
import qs.Ui as UI
import "UiLogic.js" as Logic

ColumnLayout {
    id: root
    required property var controller
    readonly property var bridge: controller.bridge
    readonly property string expandedAccount: controller.managedAccount
    spacing: Style.space(10)
    function updateRows() { Logic.syncRows(rows, bridge.snapshot.accounts) }
    function reveal(item) {
        var pos = item.mapToItem(list.contentItem, 0, 0)
        if (pos.y < list.contentY) list.contentY = pos.y
        else if (pos.y + item.height > list.contentY + list.height) list.contentY = pos.y + item.height - list.height
    }
    Component.onCompleted: updateRows()
    Connections { target: root.bridge; function onSnapshotChanged() { root.updateRows() } }
    ListModel { id: rows; dynamicRoles: true }
    RowLayout {
        Layout.fillWidth: true
        UiText { text: "Google accounts"; font.bold: true; Layout.fillWidth: true }
        UiAction {
            text: root.bridge.snapshot.authentication.busy ? "Connecting…" : "Connect account"
            primary: true
            available: root.bridge.connected
            busy: root.bridge.snapshot.authentication.busy || root.bridge.isBusy("accounts.add")
            onClicked: root.controller.addAccount()
        }
    }
    UiText {
        Layout.fillWidth: true
        visible: !root.controller.currentAccount && rows.count > 0
        text: "Choose a default below, or select an account each time you upload."
        secondary: true
    }
    Item {
        Layout.fillHeight: true
        Layout.fillWidth: true
        Column {
            anchors.centerIn: parent
            width: parent.width - Style.space(20)
            spacing: Style.space(12)
            visible: rows.count === 0
            UiText { width: parent.width; text: "Connect once. Open your Office files in Drive."; font.bold: true; horizontalAlignment: Text.AlignHCenter }
            UiText { width: parent.width; text: "Choose a Google account to own your uploaded copies. Sign-in opens in your default browser."; secondary: true; horizontalAlignment: Text.AlignHCenter }
            UiText { width: parent.width; visible: !root.controller.configured; text: "This development build needs app credentials first. Custom Google setup walks you through it."; secondary: true; horizontalAlignment: Text.AlignHCenter }
            UiAction { anchors.horizontalCenter: parent.horizontalCenter; text: root.controller.configured ? "Connect Google account" : "Set up Google sign-in"; primary: true; available: root.bridge.connected; busy: root.bridge.snapshot.authentication.busy; onClicked: root.controller.addAccount() }
        }
        ListView {
            id: list
            anchors.fill: parent
            clip: true
            visible: rows.count > 0
            model: rows
            spacing: Style.space(14)
            boundsBehavior: Flickable.StopAtBounds
            QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
            delegate: Column {
                id: account
                required property var record
                required property int index
                readonly property bool isDefault: root.bridge.snapshot.default_account === record.id
                readonly property bool expanded: root.expandedAccount === record.id
                readonly property bool editing: root.controller.editingAccount === record.id
                readonly property bool removing: root.controller.removingAccount === record.id
                readonly property bool busy: root.bridge.isBusy("accounts.remove", record.id) || root.bridge.isBusy("accounts.rename", record.id) || root.bridge.isBusy("accounts.enable", record.id) || root.bridge.isBusy("accounts.disable", record.id) || root.bridge.isBusy("accounts.set-default", record.id)
                width: list.width - Style.space(12)
                spacing: Style.space(7)
                UI.PanelSeparator { width: parent.width; visible: account.index > 0 }
                RowLayout {
                    width: parent.width
                    UiText { Layout.fillWidth: true; text: account.record.label; font.bold: true; maximumLineCount: 2; elide: Text.ElideRight }
                    UiText { text: "Default"; visible: account.isDefault; color: Color.accent; secondary: true }
                }
                UiText { width: parent.width; text: account.record.email; secondary: true; visible: account.record.label !== account.record.email }
                UiText {
                    width: parent.width
                    text: !account.record.enabled ? "Paused · enable to resume uploads" : account.record.auth === "ready" ? "Connected" : account.record.auth === "keyring" ? "Login keyring is locked" : "Sign in again to resume uploads"
                    color: account.record.enabled && account.record.auth === "ready" ? Color.foreground : Color.urgent
                    secondary: true
                }
                Flow {
                    width: parent.width
                    spacing: Style.space(4)
                    UiAction { text: "Use by default"; visible: !account.isDefault && !!account.record.enabled; available: root.bridge.connected; busy: account.busy; onClicked: root.bridge.request("accounts.set-default", {id: account.record.id}) }
                    UiAction { text: "Enable account"; primary: true; visible: !account.record.enabled; available: root.bridge.connected; busy: account.busy; onClicked: root.bridge.request("accounts.enable", {id: account.record.id}) }
                    UiAction { text: "Sign in again"; primary: true; visible: account.record.auth !== "ready" && account.record.auth !== "keyring"; available: root.bridge.connected; busy: account.busy || root.bridge.snapshot.authentication.busy; onClicked: root.bridge.request("accounts.reauthenticate", {id: account.record.id}) }
                    UiAction {
                        text: account.expanded ? "Done" : "Manage"
                        onClicked: {
                            root.controller.managedAccount = account.expanded ? "" : account.record.id
                            root.controller.editingAccount = ""
                            root.controller.removingAccount = ""
                        }
                    }
                }
                Column {
                    width: parent.width
                    visible: account.expanded
                    spacing: Style.space(8)
                    Flow {
                        width: parent.width
                        spacing: Style.space(4)
                        UiAction {
                            text: "Rename"
                            available: !account.busy
                            onClicked: {
                                root.controller.accountDraft = account.record.label
                                root.controller.editingAccount = account.record.id
                                root.controller.removingAccount = ""
                                Qt.callLater(function() { rename.forceActiveFocus(); rename.selectAll() })
                            }
                        }
                        UiAction { text: "Pause uploads"; visible: !!account.record.enabled; available: root.bridge.connected; busy: account.busy; tooltipText: "Pause this account’s uploads until you enable it again"; onClicked: root.bridge.request("accounts.disable", {id: account.record.id}) }
                        UiAction { text: "Sign in again"; visible: account.record.auth === "ready"; available: root.bridge.connected; busy: account.busy || root.bridge.snapshot.authentication.busy; onClicked: root.bridge.request("accounts.reauthenticate", {id: account.record.id}) }
                        UiAction { text: "Remove account…"; destructive: true; available: !account.busy; onClicked: { root.controller.removingAccount = account.record.id; root.controller.editingAccount = "" } }
                    }
                    Column {
                        width: parent.width
                        visible: account.editing
                        spacing: Style.space(5)
                        UiText { text: "Account name"; secondary: true }
                        UI.TextField {
                            id: rename
                            objectName: "account-name-" + account.record.id
                            width: parent.width
                            text: account.editing ? root.controller.accountDraft : ""
                            placeholderText: "For example, Personal or Work"
                            maximumLength: 80
                            enabled: !account.busy
                            Accessible.name: "Account name"
                            onTextEdited: root.controller.accountDraft = text
                            onAccepted: if (save.available && !save.busy) save.clicked()
                            onActiveFocusChanged: if (activeFocus) root.reveal(rename)
                            Keys.onEscapePressed: { root.controller.editingAccount = ""; root.controller.accountDraft = "" }
                        }
                        Row {
                            spacing: Style.space(5)
                            UiAction { text: "Cancel"; available: !account.busy; onClicked: { root.controller.editingAccount = ""; root.controller.accountDraft = "" } }
                            UiAction {
                                id: save
                                text: "Save name"
                                primary: true
                                available: root.bridge.connected && root.controller.accountDraft.trim().length > 0 && root.controller.accountDraft.trim() !== account.record.label
                                busy: account.busy
                                onClicked: root.bridge.request("accounts.rename", {id: account.record.id, label: root.controller.accountDraft.trim()})
                            }
                        }
                    }
                    Column {
                        width: parent.width
                        visible: account.removing
                        spacing: Style.space(6)
                        UiText { width: parent.width; text: "Remove this account and cancel its pending uploads? Files already in Drive are kept." }
                        UiText { width: parent.width; text: "This is your default. You will need to choose another account for future uploads."; visible: account.isDefault; secondary: true }
                        Row {
                            spacing: Style.space(5)
                            UiAction { text: "Keep account"; available: !account.busy; onClicked: root.controller.removingAccount = "" }
                            UiAction { text: account.busy ? "Removing…" : "Remove account"; destructive: true; primary: true; available: root.bridge.connected; busy: account.busy; onClicked: root.bridge.request("accounts.remove", {id: account.record.id}) }
                        }
                    }
                }
            }
        }
    }
    UiText { Layout.fillWidth: true; text: "Your browser may be signed in to a different Google account. Switch to the upload owner in Google if asked."; secondary: true }
}
