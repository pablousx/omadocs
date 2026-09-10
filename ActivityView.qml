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
    readonly property var themeFont: Style.font
    readonly property var popupPalette: Color.popups
    property int visibleLimit: 50
    property double now: Date.now()
    readonly property int matchingCount: Logic.visibleJobs(bridge.snapshot.operations, controller.activityFilter, 2000).length
    spacing: Style.space(10)
    function updateRows() { Logic.syncRows(rows, Logic.visibleJobs(bridge.snapshot.operations, controller.activityFilter, visibleLimit)) }
    function reveal(item) {
        var pos = item.mapToItem(list.contentItem, 0, 0)
        if (pos.y < list.contentY) list.contentY = pos.y
        else if (pos.y + item.height > list.contentY + list.height) list.contentY = pos.y + item.height - list.height
    }
    function batchCount(batch) {
        return bridge.snapshot.operations.filter(function(job) { return job.batch === batch && job.state === "waiting_account" }).length
    }
    Component.onCompleted: updateRows()
    onVisibleLimitChanged: updateRows()
    Connections { target: root.bridge; function onSnapshotChanged() { root.updateRows() } }
    Connections {
        target: root.controller
        function onActivityFilterChanged() { root.visibleLimit = 50; root.updateRows(); list.positionViewAtBeginning() }
    }
    Timer { interval: 60000; repeat: true; running: root.visible; onTriggered: root.now = Date.now() }
    ListModel { id: rows; dynamicRoles: true }

    RowLayout {
        Layout.fillWidth: true
        UiText { Layout.fillWidth: true; text: root.bridge.snapshot.active ? root.bridge.snapshot.active + " in progress" : "Your uploads"; font.bold: true }
        UiAction {
            text: root.controller.selectingFiles ? "Choosing files…" : root.bridge.isBusy("open") ? "Preparing files…" : "Upload files…"
            primary: true
            available: root.bridge.connected
            busy: root.bridge.isBusy("open") || root.controller.selectingFiles
            tooltipText: "Choose DOCX, XLSX, or PPTX files · creates new Drive copies"
            onClicked: root.controller.chooseFiles()
        }
    }
    Flow {
        Layout.fillWidth: true
        spacing: Style.space(4)
        Repeater {
            model: [{key: "all", label: "All"}, {key: "attention", label: "Needs attention"}, {key: "complete", label: "Uploaded"}]
            UiAction {
                required property var modelData
                text: modelData.label + (modelData.key === "attention" && root.bridge.snapshot.attention ? " · " + root.bridge.snapshot.attention : "")
                selected: root.controller.activityFilter === modelData.key
                onClicked: root.controller.activityFilter = modelData.key
            }
        }
    }
    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Column {
            anchors.centerIn: parent
            width: Math.max(0, parent.width - Style.space(30))
            spacing: Style.space(12)
            visible: rows.count === 0
            UiText { width: parent.width; text: root.controller.activityFilter === "attention" ? "Nothing needs your attention" : root.controller.activityFilter === "complete" ? "No uploaded copies yet" : "Your documents, ready in Google Drive"; font.bold: true; horizontalAlignment: Text.AlignHCenter }
            UiText {
                width: parent.width
                text: root.controller.activityFilter !== "all" ? "New activity will appear here."
                    : !root.bridge.snapshot.accounts.length ? "Connect a Google account, then choose an Office file to upload."
                    : "Choose Upload files, or drop Office documents here. You can also use Open with → omadocs in your file manager."
                secondary: true
                horizontalAlignment: Text.AlignHCenter
            }
            UiAction {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Connect Google account"
                primary: true
                available: root.bridge.connected
                busy: root.bridge.snapshot.authentication.busy
                visible: !root.bridge.snapshot.accounts.length && root.controller.activityFilter === "all"
                onClicked: root.controller.addAccount()
            }
            UiAction { anchors.horizontalCenter: parent.horizontalCenter; text: "Show all uploads"; visible: root.controller.activityFilter !== "all"; onClicked: root.controller.activityFilter = "all" }
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
                id: job
                required property var record
                required property int index
                property bool confirmingCancel: false
                readonly property bool canCancel: ["complete", "cancelled", "expired"].indexOf(record.state) < 0
                readonly property bool busy: root.bridge.isBusy("activity.retry", record.id) || root.bridge.isBusy("activity.cancel", record.id) || root.bridge.isBusy("activity.reopen", record.id) || root.bridge.isBusy("activity.assign", record.id)
                readonly property bool sourceError: ["local_file", "source_changed"].indexOf(record.error) >= 0 && record.state === "failed"
                width: list.width - Style.space(12)
                spacing: Style.space(6)
                UI.PanelSeparator { width: parent.width; visible: job.index > 0 }
                RowLayout {
                    width: parent.width
                    UiText { text: "\uf15c"; color: Color.accent; Layout.alignment: Qt.AlignTop }
                    UiText { Layout.fillWidth: true; text: job.record.name; font.bold: true; maximumLineCount: 2; elide: Text.ElideMiddle }
                    UiText { text: Logic.relativeTime(job.record.created, root.now); secondary: true; Layout.alignment: Qt.AlignTop }
                }
                UiText {
                    width: parent.width
                    text: Logic.stateLabel(job.record) + (job.record.state === "uploading" ? " · " + Math.floor(100 * Logic.progress(job.record)) + "%" : "")
                    color: Logic.needsAttention(job.record) ? Color.urgent : Color.foreground
                }
                Rectangle {
                    width: parent.width
                    height: Style.space(4)
                    radius: height / 2
                    visible: job.record.state === "uploading"
                    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.14)
                    Rectangle {
                        height: parent.height
                        width: parent.width * Logic.progress(job.record)
                        radius: height / 2
                        color: Color.accent
                        Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                    }
                    Accessible.role: Accessible.ProgressBar
                    Accessible.name: "Upload progress"
                    Accessible.description: Math.floor(100 * Logic.progress(job.record)) + "%"
                }
                UiText {
                    width: parent.width
                    text: [job.record.owner || "No account selected", Logic.fileSize(job.record.size)].filter(function(value) { return !!value }).join(" · ")
                    secondary: true
                    maximumLineCount: 2
                    elide: Text.ElideMiddle
                }
                UiText {
                    width: parent.width
                    visible: !!job.record.error && job.record.state !== "cancelled"
                    text: Logic.errorText(job.record.error)
                    secondary: true
                }
                UiText {
                    width: parent.width
                    visible: job.record.state === "complete" && ["failed", "uncertain"].indexOf(job.record.browser) >= 0
                    text: "Your copy is safe in Drive. Open it again without uploading another copy."
                    secondary: true
                }
                Flow {
                    width: parent.width
                    spacing: Style.space(4)
                    UiAction {
                        text: root.bridge.isBusy("activity.reopen", job.record.id) ? "Opening…" : "Open in browser"
                        primary: true
                        visible: job.record.state === "complete"
                        available: root.bridge.connected && ["pending", "launching"].indexOf(job.record.browser) < 0
                        busy: job.busy
                        tooltipText: "Open this existing Drive copy; no new upload"
                        onClicked: root.bridge.request("activity.reopen", {id: job.record.id})
                    }
                    UiAction {
                        text: "Sign in again"
                        primary: true
                        visible: job.record.state === "auth_required" && job.record.error !== "keyring"
                        available: root.bridge.connected && !!root.controller.account(job.record.account)
                        busy: root.bridge.snapshot.authentication.busy || job.busy
                        onClicked: root.bridge.request("accounts.reauthenticate", {id: job.record.account})
                    }
                    UiAction {
                        text: "Enable account"
                        primary: true
                        visible: job.record.state === "paused"
                        available: root.bridge.connected
                        busy: root.bridge.isBusy("accounts.enable", job.record.account) || job.busy
                        onClicked: root.bridge.request("accounts.enable", {id: job.record.account})
                    }
                    UiAction {
                        text: job.record.state === "unresolved" ? "Check Drive copy" : "Retry upload"
                        primary: true
                        visible: !job.sourceError && (["failed", "unresolved"].indexOf(job.record.state) >= 0 || job.record.state === "auth_required" && job.record.error === "keyring")
                        available: root.bridge.connected
                        busy: job.busy
                        onClicked: root.bridge.request("activity.retry", {id: job.record.id})
                    }
                    UiAction {
                        text: "Choose file again…"
                        visible: job.sourceError || job.record.state === "expired"
                        available: root.bridge.connected
                        onClicked: root.controller.chooseFiles()
                    }
                    UiAction {
                        id: cancelAction
                        text: root.bridge.isBusy("activity.cancel", job.record.id) ? "Cancelling…" : "Cancel"
                        visible: job.canCancel && !job.confirmingCancel
                        available: root.bridge.connected
                        busy: job.busy
                        onClicked: { job.confirmingCancel = true; Qt.callLater(function() { keepUpload.forceActiveFocus() }) }
                    }
                }
                Column {
                    width: parent.width
                    visible: job.confirmingCancel && job.canCancel
                    spacing: Style.space(5)
                    UiText { width: parent.width; text: "Cancel this upload? A copy already received by Google will stay in Drive."; secondary: true }
                    Row {
                        spacing: Style.space(5)
                        UiAction { id: keepUpload; text: "Keep upload"; onClicked: { job.confirmingCancel = false; Qt.callLater(function() { cancelAction.forceActiveFocus() }) } }
                        UiAction { text: "Cancel upload"; destructive: true; busy: job.busy; available: root.bridge.connected; onClicked: root.bridge.request("activity.cancel", {id: job.record.id}) }
                    }
                    Keys.onEscapePressed: { job.confirmingCancel = false; Qt.callLater(function() { cancelAction.forceActiveFocus() }) }
                }
                Column {
                    width: parent.width
                    visible: job.record.state === "waiting_account"
                    spacing: Style.space(5)
                    UiText { width: parent.width; text: root.batchCount(job.record.batch) > 1 ? "One choice applies to all " + root.batchCount(job.record.batch) + " files opened together." : "Choose who will own this Drive copy."; secondary: true }
                    Repeater {
                        model: job.record.state === "waiting_account" ? root.bridge.snapshot.accounts : []
                        UiAction {
                            required property var modelData
                            text: "Upload to " + (modelData.label.length > 35 ? modelData.label.slice(0, 32) + "…" : modelData.label) + (modelData.enabled ? "" : " (paused)")
                            tooltipText: modelData.email
                            available: root.bridge.connected && !!modelData.enabled
                            busy: job.busy
                            onClicked: root.bridge.request("activity.assign", {id: job.record.id, account: modelData.id})
                        }
                    }
                    UiAction { text: root.bridge.snapshot.accounts.length ? "Manage accounts" : "Connect Google account"; available: root.bridge.connected; onClicked: root.controller.tab = 1 }
                }
            }
            footer: UiAction {
                text: "Show more uploads"
                visible: root.matchingCount > rows.count
                height: visible ? implicitHeight : 0
                onClicked: root.visibleLimit += 50
            }
        }
        DropArea {
            id: drop
            anchors.fill: parent
            enabled: root.bridge.connected && !root.bridge.isBusy("open") && !root.controller.selectingFiles
            onEntered: drag => { drag.accepted = drag.hasUrls }
            onDropped: event => {
                if (event.hasUrls) { root.controller.uploadFiles(event.urls); event.acceptProposedAction() }
            }
        }
        Rectangle {
            anchors.fill: parent
            visible: drop.containsDrag
            color: root.popupPalette.background
            border.color: Color.accent
            radius: Style.cornerRadius
            UiText { anchors.centerIn: parent; text: "Drop Office files to upload new Drive copies"; width: parent.width - Style.space(30); horizontalAlignment: Text.AlignHCenter }
        }
    }
}
