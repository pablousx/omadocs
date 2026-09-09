pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import qs.Commons
import qs.Ui as UI

UI.Panel {
    id: root
    moduleName: "io.github.pablousx.omadocs"
    manageIpc: false
    property Item anchorItem: null
    property Item hostWidget: null
    required property var bridge
    readonly property var themeFont: Style.font
    property int tab: 0
    property string removeAccount: ""
    readonly property var tabs: ["Accounts", "Uploads", "Authentication", "MIME handlers", "Settings", "Diagnostics"]
    function accountName(id) {
        for (var account of bridge.snapshot.accounts) if (account.id === id) return account.label
        return "Choose account"
    }
    function friendlyError(code) {
        var messages = {
            authentication: "Reauthenticate this Google account to continue.",
            account_mismatch: "The Google account did not match. Reauthenticate with the original account.",
            keyring: "Unlock your login keyring and retry.",
            credentials_required: "Production OAuth credentials are not configured. See the OAuth setup guide.",
            offline: "Connection interrupted. Retry when online.",
            quota: "Google quota or rate limit. Check storage or retry later.",
            permission: "Google refused access. Check organization or account permissions.",
            local_file: "Cannot read a supported, stable Office file. Check access and free space.",
            source_changed: "The source changed while copying. Save it and open it again.",
            snapshot_missing: "The temporary copy expired or is missing. This operation cannot upload again.",
            invalid_response: "Unexpected Google response. The browser was not opened.",
            auth_cancelled: "Authorization was cancelled or timed out.",
            auth_browser: "The default browser could not open authorization.",
            account_disabled: "Enable the account to continue.",
            cancelled: "Cancelled. Any completed Drive copy remains in Drive.",
            internal: "Action failed. Check redacted diagnostics."
        }
        return messages[code] || String(code || "")
    }
    onOpenedChanged: if (opened && bridge.connected) bridge.request("mime.status", {})

    component Label: Text {
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: root.themeFont.family
        font.pixelSize: root.themeFont.body
        wrapMode: Text.WordWrap
    }
    component Action: UI.Button { focusable: true; bordered: true }

    UI.KeyboardPanel {
        id: surface
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keys
        contentWidth: fittedContentWidth(Style.space(580))
        contentHeight: fittedContentHeight(Math.max(content.implicitHeight, Style.space(260)))

        UI.PanelKeyCatcher {
            id: keys
            anchors.fill: parent
            blocked: true // Native Tab traversal and text editing; Escape bubbles up.
            Keys.onEscapePressed: root.close()
            ColumnLayout {
                id: content
                anchors.fill: parent
                spacing: Style.space(10)
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "omadocs"; font.pixelSize: root.themeFont.subtitle; font.bold: true; Layout.fillWidth: true }
                    Action { text: "Close"; onClicked: root.close() }
                }
                Label {
                    Layout.fillWidth: true
                    text: "Each open uploads a new Drive copy. Your local file stays unchanged. Browser edits stay in Drive."
                    font.pixelSize: root.themeFont.caption
                    opacity: 0.8
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Style.space(5)
                    Repeater {
                        model: root.tabs
                        Action {
                            required property int index
                            required property string modelData
                            text: modelData
                            selected: root.tab === index
                            onClicked: {
                                root.tab = index
                                if (index === 5) root.bridge.request("diagnostics", {})
                            }
                        }
                    }
                }
                Label {
                    Layout.fillWidth: true
                    visible: !root.bridge.connected || root.bridge.error !== "" || !!root.bridge.snapshot.authentication.error
                    text: root.bridge.connected ? (root.bridge.error || root.friendlyError(root.bridge.snapshot.authentication.error)) : "Connecting to the omadocs helper…"
                    color: Color.urgent
                }
                QQC.ScrollView {
                    id: scroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: Math.min(pageLoader.implicitHeight, Style.space(420))
                    clip: true
                    contentWidth: availableWidth
                    Loader {
                        id: pageLoader
                        width: scroll.availableWidth
                        sourceComponent: [accountsPage, activityPage, authPage, mimePage, settingsPage, diagnosticsPage][root.tab]
                    }
                }
            }
        }
    }

    Component {
        id: accountsPage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "Upload account"; font.bold: true }
            Label { width: parent.width; text: "Default: " + root.accountName(root.bridge.snapshot.default_account) }
            Action { text: "Add Google account"; enabled: !root.bridge.snapshot.authentication.busy; onClicked: root.bridge.request("accounts.add", {}) }
            Label { width: parent.width; visible: root.bridge.snapshot.accounts.length === 0; text: "Add an account, then enable the file handlers in MIME handlers."; opacity: 0.8 }
            Repeater {
                model: root.bridge.snapshot.accounts
                Column {
                    id: accountRow
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(6)
                    UI.PanelSeparator { width: parent.width }
                    Label { width: parent.width; text: accountRow.modelData.email; font.bold: true }
                    Label {
                        width: parent.width
                        text: (accountRow.modelData.enabled ? "Enabled" : "Disabled") + " · " + accountRow.modelData.auth + (root.bridge.snapshot.default_account === accountRow.modelData.id ? " · Default" : "")
                        font.pixelSize: root.themeFont.caption
                    }
                    RowLayout {
                        width: parent.width
                        UI.TextField { id: rename; Layout.fillWidth: true; text: accountRow.modelData.label; maximumLength: 80; placeholderText: "Account label" }
                        Action { text: "Rename"; onClicked: root.bridge.request("accounts.rename", { id: accountRow.modelData.id, label: rename.text }) }
                    }
                    Flow {
                        width: parent.width
                        spacing: Style.space(5)
                        Action { text: "Set default"; enabled: !!accountRow.modelData.enabled; onClicked: root.bridge.request("accounts.set-default", { id: accountRow.modelData.id }) }
                        Action { text: "Reauthenticate"; enabled: !root.bridge.snapshot.authentication.busy; onClicked: root.bridge.request("accounts.reauthenticate", { id: accountRow.modelData.id }) }
                        Action { text: accountRow.modelData.enabled ? "Disable" : "Enable"; onClicked: root.bridge.request(accountRow.modelData.enabled ? "accounts.disable" : "accounts.enable", { id: accountRow.modelData.id }) }
                        Action { text: "Remove"; onClicked: root.removeAccount = accountRow.modelData.id }
                    }
                    Column {
                        width: parent.width
                        visible: root.removeAccount === accountRow.modelData.id
                        spacing: Style.space(5)
                        Label { width: parent.width; text: "Remove local credentials and cancel pending uploads? Drive files remain." }
                        Row {
                            spacing: Style.space(5)
                            Action { text: "Remove account"; onClicked: { root.bridge.request("accounts.remove", { id: accountRow.modelData.id }); root.removeAccount = "" } }
                            Action { text: "Keep account"; onClicked: root.removeAccount = "" }
                        }
                    }
                }
            }
        }
    }
    Component {
        id: activityPage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "Upload activity"; font.bold: true }
            Label { width: parent.width; visible: root.bridge.snapshot.operations.length === 0; text: "No uploads yet. Open a DOCX, XLSX, or PPTX file with omadocs."; opacity: 0.8 }
            Repeater {
                model: root.bridge.snapshot.operations
                Column {
                    id: job
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(6)
                    UI.PanelSeparator { width: parent.width }
                    Label { width: parent.width; text: job.modelData.name; font.bold: true }
                    Label { width: parent.width; text: "Owner: " + (job.modelData.owner || "Choose an upload account"); font.pixelSize: root.themeFont.caption }
                    Label { width: parent.width; text: job.modelData.state.replace(/_/g, " ") + (job.modelData.size ? " · " + Math.floor(100 * job.modelData.progress / job.modelData.size) + "%" : "") }
                    Rectangle {
                        width: parent.width
                        height: Style.space(3)
                        visible: job.modelData.state === "uploading"
                        color: Qt.darker(Color.foreground, 3)
                        Rectangle { height: parent.height; width: parent.width * (job.modelData.size ? job.modelData.progress / job.modelData.size : 0); color: Color.accent }
                    }
                    Label { width: parent.width; visible: !!job.modelData.error; text: root.friendlyError(job.modelData.error); color: Color.urgent; font.pixelSize: root.themeFont.caption }
                    Label { width: parent.width; visible: job.modelData.state === "complete" && ["failed", "uncertain"].indexOf(job.modelData.browser) >= 0; text: "Uploaded. Browser opening " + job.modelData.browser + ". Reopen uses this existing copy."; font.pixelSize: root.themeFont.caption }
                    Flow {
                        width: parent.width
                        spacing: Style.space(5)
                        Action { text: "Reopen"; visible: job.modelData.state === "complete"; onClicked: root.bridge.request("activity.reopen", { id: job.modelData.id }) }
                        Action { text: "Retry"; visible: ["failed", "auth_required", "paused", "unresolved"].indexOf(job.modelData.state) >= 0; onClicked: root.bridge.request("activity.retry", { id: job.modelData.id }) }
                        Action { text: "Cancel"; visible: ["complete", "cancelled", "expired"].indexOf(job.modelData.state) < 0; onClicked: root.bridge.request("activity.cancel", { id: job.modelData.id }) }
                    }
                    Column {
                        width: parent.width
                        visible: job.modelData.state === "waiting_account"
                        spacing: Style.space(5)
                        Repeater {
                            model: root.bridge.snapshot.accounts
                            Action {
                                required property var modelData
                                text: "Upload to " + modelData.label
                                enabled: !!modelData.enabled
                                onClicked: root.bridge.request("activity.assign", { id: job.modelData.id, account: modelData.id })
                            }
                        }
                    }
                }
            }
        }
    }
    Component {
        id: authPage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "Authentication"; font.bold: true }
            Label { width: parent.width; text: root.bridge.snapshot.authentication.busy ? "Waiting for Google authorization in your default browser…" : "Use Add account or Reauthenticate in Accounts to authorize Google Drive uploads." }
            Label { width: parent.width; visible: !!root.bridge.snapshot.authentication.error; text: root.friendlyError(root.bridge.snapshot.authentication.error); color: Color.urgent }
            Label { width: parent.width; text: "Only drive.file access is requested. Tokens are stored in your login keyring. Unlock it if authentication cannot continue." }
            Label { width: parent.width; text: "The upload account owns the copy. Your browser may be signed in to a different Google account; switch accounts in Google if needed." }
            Label { width: parent.width; text: "Advanced: import a Desktop OAuth credential file for development or a fork. Existing accounts retain their original OAuth client."; font.pixelSize: root.themeFont.caption; opacity: 0.8 }
            UI.TextField { id: credentialPath; width: parent.width; placeholderText: "Absolute path to Desktop credentials JSON" }
            Action { text: "Import credentials"; onClicked: { root.bridge.request("credentials.import", { path: credentialPath.text }); credentialPath.clear() } }
        }
    }
    Component {
        id: mimePage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "File handlers"; font.bold: true }
            Label { width: parent.width; text: "Make double-clicking an Office file upload a new copy to your default Google account." }
            Repeater {
                model: root.bridge.mime.handlers
                Label { required property var modelData; width: parent.width; text: modelData.extension.toUpperCase() + " → " + (modelData.current || "System fallback") }
            }
            Flow {
                width: parent.width
                spacing: Style.space(5)
                Action { text: "Use omadocs"; onClicked: root.bridge.request("mime.install", {}) }
                Action { text: "Restore previous handlers"; onClicked: root.bridge.request("mime.remove", {}) }
                Action { text: "Refresh"; onClicked: root.bridge.request("mime.status", {}) }
            }
            Label { width: parent.width; text: "Restoration applies only while omadocs is still the current handler. Later changes you make are preserved."; font.pixelSize: root.themeFont.caption; opacity: 0.8 }
        }
    }
    Component {
        id: settingsPage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "Settings"; font.bold: true }
            UI.Toggle {
                width: parent.width
                label: "Choose account for every open"
                description: "Off: use the default account."
                checked: root.bridge.snapshot.settings.choose_account === true
                onClicked: root.bridge.request("settings.set", { key: "choose_account", value: !checked })
            }
            UI.NumberField { label: "Recent uploads retained"; from: 1; to: 1000; value: root.bridge.snapshot.settings.recent_limit || 100; onModified: value => root.bridge.request("settings.set", { key: "recent_limit", value: value }) }
            UI.NumberField { label: "Recent activity lifetime (days)"; from: 1; to: 365; value: root.bridge.snapshot.settings.recent_days || 30; onModified: value => root.bridge.request("settings.set", { key: "recent_days", value: value }) }
            UI.NumberField { label: "Temporary upload lifetime (days)"; from: 1; to: 7; value: root.bridge.snapshot.settings.snapshot_days || 7; onModified: value => root.bridge.request("settings.set", { key: "snapshot_days", value: value }) }
            Label { width: parent.width; text: "Temporary copies are deleted after completion or cancellation. Expired copies are never silently replaced from the source."; font.pixelSize: root.themeFont.caption }
        }
    }
    Component {
        id: diagnosticsPage
        Column {
            width: parent.width
            spacing: Style.space(12)
            Label { width: parent.width; text: "Redacted diagnostics"; font.bold: true }
            Action { text: "Refresh diagnostics"; onClicked: root.bridge.request("diagnostics", {}) }
            Label { width: parent.width; text: JSON.stringify(root.bridge.diagnostics, null, 2); font.pixelSize: root.themeFont.caption }
            Label { width: parent.width; text: "Create a redacted support bundle from the terminal:\nomadocs support-bundle --output /path/to/support.tar.gz"; font.pixelSize: root.themeFont.caption }
        }
    }
}
