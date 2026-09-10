pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import qs.Commons
import qs.Ui as UI
import "UiLogic.js" as Logic

QQC.ScrollView {
    id: root
    required property var controller
    readonly property var bridge: controller.bridge
    readonly property var themeFont: Style.font
    readonly property var scroller: contentItem
    readonly property string section: controller.settingsSection || "none"
    readonly property bool allInstalled: bridge.mime.handlers.length === 3 && bridge.mime.handlers.every(function(item) { return item.installed })
    readonly property bool mimeBusy: bridge.isBusy("mime.install") || bridge.isBusy("mime.remove") || bridge.isBusy("mime.status")
    property bool showDetails: false
    clip: true
    contentWidth: availableWidth
    function toggleSection(value) {
        controller.settingsSection = section === value ? "none" : value
        if (value === "diagnostics" && controller.settingsSection === value) bridge.request("diagnostics", {})
    }
    function reveal(item) {
        var flick = root.scroller
        var pos = item.mapToItem(content, 0, 0)
        if (pos.y < flick.contentY) flick.contentY = pos.y
        else if (pos.y + item.height > flick.contentY + root.height) flick.contentY = pos.y + item.height - root.height
    }
    Component.onCompleted: if (section === "diagnostics") bridge.request("diagnostics", {})

    Column {
        id: content
        width: root.availableWidth - Style.space(12)
        spacing: Style.space(12)
        UI.Toggle {
            width: parent.width
            label: "Ask which account to use"
            description: "Choose once for each file or group of files you open."
            checked: root.bridge.snapshot.settings.choose_account === true
            enabled: root.bridge.connected && !root.bridge.isBusy("settings.set", "choose_account")
            opacity: enabled ? 1 : 0.5
            Accessible.name: label
            onClicked: root.bridge.request("settings.set", {key: "choose_account", value: !checked})
            onActiveFocusChanged: if (activeFocus) root.reveal(this)
        }
        UI.PanelSeparator { width: parent.width }
        UiAction { text: (root.section === "files" ? "− " : "+ ") + "File opening" + (root.allInstalled ? " · Enabled" : ""); width: parent.width; leftAlign: true; onClicked: root.toggleSection("files") }
        Column {
            width: parent.width
            visible: root.section === "files"
            spacing: Style.space(9)
            UiText { width: parent.width; text: root.allInstalled ? "Double-click Office files to upload them with omadocs." : "Choose whether Office files open with omadocs by default." }
            UiText { width: parent.width; text: "Every double-click uploads a separate copy. You can always use Open with → omadocs without changing your defaults."; secondary: true }
            Repeater {
                model: root.bridge.mime.handlers
                RowLayout {
                    id: handler
                    required property var modelData
                    width: parent.width
                    UiText { text: handler.modelData.extension.replace(".", "").toUpperCase(); font.bold: true }
                    UiText { Layout.fillWidth: true; text: handler.modelData.installed ? "omadocs" : Logic.handlerName(handler.modelData.current); secondary: true; horizontalAlignment: Text.AlignRight; maximumLineCount: 1; elide: Text.ElideRight }
                }
            }
            Flow {
                width: parent.width
                spacing: Style.space(5)
                UiAction { text: "Use omadocs by default"; primary: true; visible: !root.allInstalled; available: root.bridge.connected; busy: root.mimeBusy; onClicked: root.bridge.request("mime.install", {}) }
                UiAction { text: "Restore previous defaults"; available: root.bridge.connected && root.bridge.mime.restoration_pending; busy: root.mimeBusy; onClicked: root.bridge.request("mime.remove", {}) }
                UiAction { text: "Refresh"; available: root.bridge.connected; busy: root.mimeBusy; onClicked: root.bridge.request("mime.status", {}) }
            }
            UiText { width: parent.width; text: "Restoring keeps any app choices you made after enabling omadocs."; secondary: true }
        }
        UI.PanelSeparator { width: parent.width }
        UiAction { text: (root.section === "google" ? "− " : "+ ") + "Custom Google setup" + (root.controller.configured ? " · Ready" : ""); width: parent.width; leftAlign: true; onClicked: root.toggleSection("google") }
        Column {
            width: parent.width
            visible: root.section === "google"
            spacing: Style.space(9)
            UiText { width: parent.width; text: root.controller.configured ? "Google sign-in is configured." : "One-time setup for this development build"; font.bold: true }
            UiText {
                width: parent.width
                text: root.controller.configured ? "Accounts are ready to connect. Import another client below only for development or a fork; existing accounts keep their original client."
                    : "1. Enable Google Drive API in a Google Cloud project.\n2. Create a Desktop OAuth client and add your email as a test user.\n3. Download the JSON and import it below."
                secondary: true
            }
            UiAction { text: "Google’s setup instructions ↗"; onClicked: Qt.openUrlExternally("https://developers.google.com/workspace/drive/api/quickstart/python#authorize_credentials_for_a_desktop_application") }
            UiText { text: "Desktop OAuth JSON file"; secondary: true }
            UI.TextField {
                id: credential
                width: parent.width
                text: root.controller.credentialDraft
                placeholderText: "/home/you/Downloads/desktop-client.json"
                enabled: !root.bridge.isBusy("credentials.import")
                Accessible.name: "Desktop OAuth JSON file path"
                onTextEdited: root.controller.credentialDraft = text
                onAccepted: if (importButton.available && !importButton.busy) importButton.clicked()
                onActiveFocusChanged: if (activeFocus) root.reveal(credential)
            }
            Flow {
                width: parent.width
                spacing: Style.space(5)
                UiAction { text: "Browse…"; available: !root.bridge.isBusy("credentials.import") && !root.controller.selectingFiles; onClicked: root.controller.chooseCredentials() }
                UiAction {
                    id: importButton
                    text: root.bridge.isBusy("credentials.import") ? "Importing…" : "Import credentials"
                    primary: !root.controller.configured
                    available: root.bridge.connected && root.controller.credentialDraft.trim().charAt(0) === "/"
                    busy: root.bridge.isBusy("credentials.import")
                    onClicked: root.bridge.request("credentials.import", {path: root.controller.credentialDraft.trim()})
                }
                UiAction { text: "Connect account"; primary: true; visible: root.controller.configured; available: root.bridge.connected; busy: root.bridge.snapshot.authentication.busy; onClicked: root.controller.addAccount() }
            }
            UiText { width: parent.width; text: "Access is limited to files created or authorized for this app. Sign-in tokens stay in your login keyring."; secondary: true }
        }
        UI.PanelSeparator { width: parent.width }
        UiAction { text: (root.section === "history" ? "− " : "+ ") + "Activity history"; width: parent.width; leftAlign: true; onClicked: root.toggleSection("history") }
        Column {
            width: parent.width
            visible: root.section === "history"
            spacing: Style.space(12)
            UiText { width: parent.width; text: "Changes save automatically. Clearing old activity never removes files from Google Drive."; secondary: true }
            UI.NumberField {
                label: "Keep up to this many recent uploads"
                from: 1; to: 1000
                value: root.bridge.snapshot.settings.recent_limit || 100
                enabled: root.bridge.connected && !root.bridge.isBusy("settings.set", "recent_limit")
                onModified: value => root.bridge.request("settings.set", {key: "recent_limit", value: value})
            }
            UI.NumberField {
                label: "Keep recent activity for this many days"
                from: 1; to: 365
                value: root.bridge.snapshot.settings.recent_days || 30
                enabled: root.bridge.connected && !root.bridge.isBusy("settings.set", "recent_days")
                onModified: value => root.bridge.request("settings.set", {key: "recent_days", value: value})
            }
            UI.NumberField {
                label: "Keep unfinished upload copies for this many days"
                from: 1; to: 7
                value: root.bridge.snapshot.settings.snapshot_days || 7
                enabled: root.bridge.connected && !root.bridge.isBusy("settings.set", "snapshot_days")
                onModified: value => root.bridge.request("settings.set", {key: "snapshot_days", value: value})
            }
            UiText { width: parent.width; text: "Temporary copies are deleted after completion or cancellation. Open in browser is available while an uploaded item remains in activity."; secondary: true }
        }
        UI.PanelSeparator { width: parent.width }
        UiAction { text: (root.section === "diagnostics" ? "− " : "+ ") + "Diagnostics"; width: parent.width; leftAlign: true; onClicked: root.toggleSection("diagnostics") }
        Column {
            width: parent.width
            visible: root.section === "diagnostics"
            spacing: Style.space(9)
            UiText { width: parent.width; text: "Safe to share: no document names, account emails, file paths, or credentials."; secondary: true }
            Flow {
                width: parent.width
                spacing: Style.space(5)
                UiAction { text: "Refresh"; available: root.bridge.connected; busy: root.bridge.isBusy("diagnostics"); onClicked: root.bridge.request("diagnostics", {}) }
                UiAction {
                    text: "Copy diagnostics"
                    available: !!root.bridge.diagnostics.version
                    onClicked: { details.selectAll(); details.copy(); details.deselect(); root.bridge.tell("Redacted diagnostics copied.") }
                }
                UiAction { text: root.showDetails ? "Hide details" : "Show details"; onClicked: root.showDetails = !root.showDetails }
            }
            UiText { width: parent.width; text: root.bridge.diagnostics.version ? "omadocs " + root.bridge.diagnostics.version + " · " + root.bridge.diagnostics.accounts + " connected account(s)" : "Loading diagnostics…"; secondary: true }
            QQC.TextArea {
                id: details
                width: parent.width
                visible: root.showDetails
                text: JSON.stringify(root.bridge.diagnostics, null, 2)
                textFormat: TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                font.family: root.themeFont.family
                font.pixelSize: root.themeFont.caption
                color: Color.foreground
                selectionColor: Color.accent
                selectedTextColor: Color.background
                background: Rectangle { color: "transparent" }
                Accessible.name: "Redacted diagnostics"
                onActiveFocusChanged: if (activeFocus) root.reveal(details)
            }
        }
    }
}
