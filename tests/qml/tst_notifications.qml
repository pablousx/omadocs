import QtQuick
import QtQuick.Layouts
import QtTest
import "../.." as App

Item {
    width: 570
    height: 510
    Component {
        id: hostComponent
        ColumnLayout {
            width: 550
            height: 490
            property int tab: 0
            property alias footer: footer
            property alias page: page
            FakeController { id: fakeController }
            Loader {
                id: page
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: [uploads, accounts, settings][parent.tab]
            }
            App.NotificationFooter {
                id: footer
                Layout.fillWidth: true
                Layout.minimumHeight: implicitHeight
                Layout.preferredHeight: implicitHeight
                Layout.maximumHeight: implicitHeight
            }
            Component { id: uploads; App.ActivityView { controller: fakeController } }
            Component { id: accounts; App.AccountsView { controller: fakeController } }
            Component { id: settings; App.SettingsView { controller: fakeController } }
        }
    }
    TestCase {
        name: "OmadocsNotifications"
        when: windowShown
        function init() { failOnWarning(/.?/) }
        function geometry(item) { return [item.x, item.y, item.width, item.height] }
        function test_stable_content_data() {
            return [{tag: "uploads", tab: 0}, {tag: "accounts", tab: 1}, {tag: "settings", tab: 2}]
        }
        function test_stable_content(data) {
            var host = createTemporaryObject(hostComponent, parent, {tab: data.tab})
            verify(host !== null)
            wait(50)
            var before = geometry(host.page)
            var footerBefore = geometry(host.footer)
            var states = [
                {message: "Files added to Uploads.", dismissible: true},
                {message: "Reconnecting… Existing uploads are kept."},
                {message: "Finish Google sign-in in your browser…"},
                {message: "Google sign-in needs a one-time app setup. ".repeat(12), error: true, dismissible: true, setupAvailable: true},
                {message: ""}
            ]
            for (var state of states) {
                host.footer.message = state.message
                host.footer.error = !!state.error
                host.footer.dismissible = !!state.dismissible
                host.footer.setupAvailable = !!state.setupAvailable
                wait(20)
                compare(geometry(host.page), before)
                compare(geometry(host.footer), footerBefore)
            }
        }
        function test_truncation_tooltip_and_actions() {
            var host = createTemporaryObject(hostComponent, parent)
            host.footer.message = "A long actionable error message. ".repeat(30)
            host.footer.dismissible = true
            host.footer.setupAvailable = true
            var dismissed = 0, setup = 0
            host.footer.dismissed.connect(function() { dismissed++ })
            host.footer.setupRequested.connect(function() { setup++ })
            wait(50)
            var label = findChild(host.footer, "notification-message")
            verify(label.truncated)
            compare(label.maximumLineCount, 2)
            mouseMove(label, 5, label.height / 2)
            var tooltip = findChild(host.footer, "notification-tooltip")
            tryCompare(tooltip, "visible", true)
            compare(tooltip.text, host.footer.message)
            mouseClick(action(host.footer, "Custom Google setup"))
            compare(setup, 1)
            mouseClick(action(host.footer, "Dismiss"))
            compare(dismissed, 1)
        }
        function action(item, text) {
            if (item.text === text && typeof item.clicked === "function") return item
            for (var child of item.children) {
                var found = action(child, text)
                if (found) return found
            }
            return null
        }
    }
}
