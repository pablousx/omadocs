import QtQuick
import QtTest
import "../.." as App

Item {
    width: 540
    height: 540
    Component { id: controllerComponent; FakeController {} }
    Component { id: activityComponent; App.ActivityView {} }
    Component { id: accountsComponent; App.AccountsView {} }
    Component { id: settingsComponent; App.SettingsView {} }
    TestCase {
        id: test
        name: "OmadocsViews"
        when: windowShown
        property var controller
        property var views
        function init() { failOnWarning(/.?/); controller = createTemporaryObject(controllerComponent, parent); views = [] }
        function cleanup() { for (var view of views) if (view) view.destroy(); wait(5) }
        function createView(component) {
            var view = component.createObject(parent, {controller: controller, width: 408, height: 500})
            views.push(view)
            verify(view !== null)
            wait(80)
            return view
        }
        function action(item, text) {
            if (item.text === text && typeof item.clicked === "function" && item.visible) return item
            for (var i = 0; i < item.children.length; i++) {
                var found = action(item.children[i], text)
                if (found) return found
            }
            return null
        }
        function test_activity_picker_and_filter() {
            var view = createView(activityComponent)
            var button = action(view, "Upload files…")
            verify(button !== null)
            mouseClick(button)
            compare(controller.chooserCount, 1)
            mouseClick(action(view, "Needs attention · 1"))
            compare(controller.activityFilter, "attention")
            wait(20)
            verify(action(view, "Open in browser") !== null)
        }
        function test_activity_cancel_requires_explicit_confirmation() {
            var view = createView(activityComponent)
            verify(action(view, "Cancel upload") === null)
            mouseClick(action(view, "Cancel"))
            wait(20)
            verify(action(view, "Cancel upload") !== null)
            verify(!controller.bridge.isBusy("activity.cancel"))
            mouseClick(action(view, "Keep upload"))
            wait(20)
            verify(action(view, "Cancel upload") === null)
        }
        function test_accounts_manage_and_cancel_removal() {
            var view = createView(accountsComponent)
            mouseClick(action(view, "Manage"))
            wait(20)
            mouseClick(action(view, "Remove account…"))
            compare(controller.removingAccount, "personal")
            verify(!controller.bridge.isBusy("accounts.remove"))
            wait(20)
            mouseClick(action(view, "Keep account"))
            compare(controller.removingAccount, "")
        }
        function test_credential_draft_survives_failed_import() {
            controller.settingsSection = "google"
            controller.credentialDraft = "/tmp/my-client.json"
            var view = createView(settingsComponent)
            var sent = []
            controller.bridge.send.connect(function(message) { sent.push(JSON.parse(message)) })
            action(view, "Import credentials").clicked()
            compare(controller.credentialDraft, "/tmp/my-client.json")
            verify(controller.bridge.isBusy("credentials.import"))
            controller.bridge.receive(JSON.stringify({version: 1, id: sent[0].id, error: {code: "invalid_input"}}))
            compare(controller.credentialDraft, "/tmp/my-client.json")
            verify(!controller.bridge.isBusy("credentials.import"))
        }
        function test_rename_input_and_focus_survive_background_update() {
            var view = createView(accountsComponent)
            mouseClick(action(view, "Manage"))
            wait(20)
            mouseClick(action(view, "Rename"))
            wait(20)
            var field = findChild(view, "account-name-personal")
            verify(field.activeFocus)
            keyClick(Qt.Key_H); keyClick(Qt.Key_O); keyClick(Qt.Key_M); keyClick(Qt.Key_E)
            compare(field.text, "home")
            var updated = JSON.parse(JSON.stringify(controller.bridge.snapshot))
            updated.operations[0].progress = 9000000
            controller.bridge.snapshot = updated
            wait(20)
            compare(findChild(view, "account-name-personal"), field)
            verify(field.activeFocus)
            compare(field.text, "home")
            keyClick(Qt.Key_Escape)
            compare(controller.editingAccount, "")
            verify(!controller.bridge.isBusy("accounts.rename"))
        }
        function test_disabled_and_busy_upload_button_ignore_clicks() {
            var view = createView(activityComponent)
            var button = action(view, "Upload files…")
            controller.bridge.connected = false
            mouseClick(button)
            compare(controller.chooserCount, 0)
            controller.bridge.connected = true
            controller.bridge.request("open", {files: ["file:///tmp/example.docx"]})
            mouseClick(button)
            compare(controller.chooserCount, 0)
        }
        function test_render_views() {
            var view = createView(activityComponent)
            compare(grabImage(view).width, 408)
            grabImage(view).save("/tmp/omadocs-ux-uploads.png")
            views.pop()
            view.destroy()
            wait(10)
            view = createView(accountsComponent)
            compare(grabImage(view).width, 408)
            grabImage(view).save("/tmp/omadocs-ux-accounts.png")
            views.pop()
            view.destroy()
            wait(10)
            view = createView(settingsComponent)
            compare(grabImage(view).width, 408)
            grabImage(view).save("/tmp/omadocs-ux-settings.png")
        }
    }
}
