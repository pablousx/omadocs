import QtQuick
import "../.." as App

Item {
    id: root
    property alias bridge: backend
    property int tab: 0
    property bool configured: true
    property string settingsSection: ""
    property string credentialDraft: ""
    property string editingAccount: ""
    property string managedAccount: ""
    property string accountDraft: ""
    property string removingAccount: ""
    property string activityFilter: "all"
    property bool selectingFiles: false
    property int chooserCount: 0
    property var currentAccount: account(backend.snapshot.default_account)
    function account(id) { return backend.snapshot.accounts.find(function(item) { return item.id === id }) || null }
    function chooseFiles() { chooserCount++ }
    function chooseCredentials() { chooserCount++ }
    function uploadFiles(urls) { backend.request("open", {files: urls}) }
    function addAccount() { backend.request("accounts.add", {}) }
    App.BridgeState {
        id: backend
        transportReady: true
        connected: true
        snapshot: ({
            accounts: [{id: "personal", email: "alice@example.test", label: "Personal", enabled: true, auth: "ready"},
                {id: "work", email: "work@example.test", label: "Work", enabled: false, auth: "ready"}],
            default_account: "personal", authentication: {busy: false, error: null}, setup: {client_configured: true},
            settings: {choose_account: false, recent_limit: 100, recent_days: 30, snapshot_days: 7}, active: 1, attention: 1,
            operations: [
                {id: "upload", batch: "batch1", name: "Quarterly report — México.docx", state: "uploading", progress: 5300000, size: 10000000, owner: "alice@example.test", account: "personal", created: Date.now()/1000 - 60, browser: "none", error: null},
                {id: "browser", batch: "batch2", name: "Team budget.xlsx", state: "complete", progress: 12000, size: 12000, owner: "alice@example.test", account: "personal", created: Date.now()/1000 - 120, browser: "failed", error: null},
                {id: "complete", batch: "batch3", name: "Project presentation.pptx", state: "complete", progress: 130000, size: 130000, owner: "alice@example.test", account: "personal", created: Date.now()/1000 - 240, browser: "opened", error: null}
            ]
        })
        mime: ({ handlers: [{extension: ".docx", installed: true}, {extension: ".xlsx", installed: true}, {extension: ".pptx", installed: true}], restoration_pending: true })
    }
}
