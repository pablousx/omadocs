pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui as UI
import "UiLogic.js" as Logic

UI.Panel {
    id: root
    moduleName: "io.github.pablousx.omadocs"
    manageIpc: false
    property Item anchorItem: null
    property Item hostWidget: null
    required property var bridge
    readonly property var themeFont: Style.font
    property int tab: 0
    readonly property bool selectingFiles: picker.busy
    property bool visited: false
    property int sessionHeight: 510
    property string settingsSection: ""
    property string credentialDraft: ""
    property string editingAccount: ""
    property string managedAccount: ""
    property string accountDraft: ""
    property string removingAccount: ""
    property string dismissedAuth: ""
    property string activityFilter: "all"
    readonly property bool configured: !!bridge.snapshot.setup && bridge.snapshot.setup.client_configured === true
    readonly property var currentAccount: account(bridge.snapshot.default_account)
    readonly property string authError: bridge.snapshot.authentication.error || ""
    readonly property string bannerError: bridge.error || (authError && authError !== dismissedAuth && !(authError === "credentials_required" && configured) ? Logic.errorText(authError) : "")
    readonly property string bannerCode: bridge.errorCode || authError
    readonly property string destination: bridge.snapshot.settings.choose_account ? "Choose an account for each upload"
        : currentAccount ? (currentAccount.enabled ? "Upload to " + currentAccount.label : currentAccount.label + " is paused") : "Choose an upload account"

    function account(id) {
        for (var item of bridge.snapshot.accounts) if (item.id === id) return item
        return null
    }
    function fitHeight() {
        var count = bridge.snapshot.operations.length
        sessionHeight = tab === 0 ? (count === 0 ? 350 : count === 1 ? 330 : count === 2 ? 440 : 510) : tab === 1 ? 410 : 510
    }
    function navigate(index) { tab = index }
    function googleSetup() { settingsSection = "google"; tab = 2 }
    function addAccount() {
        if (!configured) { googleSetup(); return }
        dismissedAuth = ""
        bridge.request("accounts.add", {})
    }
    function chooseFiles() {
        if (!bridge.connected || bridge.isBusy("open") || picker.busy) return
        close()
        picker.open("files")
    }
    function chooseCredentials() {
        if (picker.busy) return
        close()
        picker.open("credentials")
    }
    function uploadFiles(urls) {
        var list = []
        for (var i = 0; i < urls.length; i++) list.push(String(urls[i]))
        if (!list.length) return
        if (list.length > 64 || list.some(function(value) { return value.indexOf("file://") !== 0 })) {
            bridge.error = "Choose up to 64 local Office files at a time."
            return
        }
        tab = 0
        activityFilter = "all"
        bridge.request("open", { files: list })
    }
    function handleEscape() {
        if (removingAccount) { removingAccount = ""; return }
        if (editingAccount) { editingAccount = ""; accountDraft = ""; return }
        close()
    }
    onAuthErrorChanged: if (!authError) dismissedAuth = ""
    onTabChanged: fitHeight()
    onOpenedChanged: if (opened) {
        if (!visited) {
            tab = bridge.snapshot.accounts.length || bridge.snapshot.operations.length ? 0 : 1
            visited = true
        } else if (bridge.snapshot.operations.some(function(job) { return job.state === "waiting_account" })) {
            tab = 0
            activityFilter = "attention"
        }
        if (bridge.connected) bridge.request("mime.status", {})
        fitHeight()
    }

    FilePicker {
        id: picker
        helper: root.bridge.helper
        onSelected: urls => {
            if (kind === "credentials") root.credentialDraft = decodeURIComponent(String(urls[0]).replace(/^file:\/\//, ""))
            else { root.tab = 0; root.uploadFiles(urls) }
            root.open()
        }
        onCancelled: root.open()
        onFailed: message => { root.bridge.errorCode = ""; root.bridge.error = message; root.open() }
    }
    Connections {
        target: root.bridge
        function onReplied(method, result, params) {
            if (method === "accounts.rename") { root.editingAccount = ""; root.accountDraft = "" }
            if (method === "accounts.remove") root.removingAccount = ""
            if (method === "credentials.import") root.credentialDraft = ""
            if (method === "open") {
                var failed = result.operations.filter(function(job) { return job.state === "failed" }).length
                root.bridge.tell(failed ? "Some files need attention. See their details below." : "Files added to Uploads.")
            }
        }
    }

    UI.KeyboardPanel {
        id: surface
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keys
        contentWidth: fittedContentWidth(Style.space(570))
        contentHeight: fittedContentHeight(Style.space(root.sessionHeight))

        UI.PanelKeyCatcher {
            id: keys
            anchors.fill: parent
            blocked: true
            Keys.onEscapePressed: root.handleEscape()
            Keys.onPressed: event => {
                if (event.modifiers & Qt.ControlModifier && event.key >= Qt.Key_1 && event.key <= Qt.Key_3) {
                    root.tab = event.key - Qt.Key_1
                    event.accepted = true
                }
            }
            ColumnLayout {
                anchors.fill: parent
                spacing: Style.space(10)
                RowLayout {
                    Layout.fillWidth: true
                    UiText { text: "\uf15c"; font.pixelSize: root.themeFont.subtitle; color: Color.accent }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(2)
                        UiText { text: "omadocs"; font.pixelSize: root.themeFont.subtitle; font.bold: true }
                        UiText { Layout.fillWidth: true; text: root.bridge.connected ? root.destination : "Connecting…"; secondary: true; maximumLineCount: 1; elide: Text.ElideRight }
                    }
                    UiAction { text: "Close"; tooltipText: "Close panel · Esc"; onClicked: root.close() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(4)
                    Repeater {
                        id: navigation
                        model: ["Uploads", "Accounts", "Settings"]
                        UiAction {
                            required property int index
                            required property string modelData
                            Layout.fillWidth: true
                            text: modelData + (index === 0 && root.bridge.snapshot.active ? " · " + root.bridge.snapshot.active : "")
                            primary: root.tab === index
                            tooltipText: "Ctrl+" + (index + 1)
                            onClicked: root.navigate(index)
                            Keys.onLeftPressed: { root.tab = (index + 2) % 3; navigation.itemAt(root.tab).forceActiveFocus() }
                            Keys.onRightPressed: { root.tab = (index + 1) % 3; navigation.itemAt(root.tab).forceActiveFocus() }
                        }
                    }
                }
                Loader {
                    id: page
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    sourceComponent: [uploadsPage, accountsPage, settingsPage][root.tab]
                }
                NotificationFooter {
                    Layout.fillWidth: true
                    Layout.minimumHeight: implicitHeight
                    Layout.preferredHeight: implicitHeight
                    Layout.maximumHeight: implicitHeight
                    message: !root.bridge.connected ? "Reconnecting… Existing uploads are kept."
                        : root.bannerError || (root.bridge.snapshot.authentication.busy ? "Finish Google sign-in in your browser…" : root.bridge.notice)
                    error: !!root.bannerError
                    dismissible: !!root.bannerError || !!root.bridge.notice
                    setupAvailable: !!root.bannerError && root.bannerCode === "credentials_required"
                    onDismissed: { root.dismissedAuth = root.authError; root.bridge.dismissError(); root.bridge.notice = "" }
                    onSetupRequested: root.googleSetup()
                }
            }
        }
    }
    Component { id: uploadsPage; ActivityView { controller: root } }
    Component { id: accountsPage; AccountsView { controller: root } }
    Component { id: settingsPage; SettingsView { controller: root } }
}
