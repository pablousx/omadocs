import QtQuick
import QtTest
import "../.." as App
import "../../UiLogic.js" as Logic

Item {
    width: 540
    height: 600
    Component { id: bridgeComponent; App.BridgeState { transportReady: true } }
    ListModel { id: rows; dynamicRoles: true }
    TestCase {
        id: test
        name: "OmadocsInteractions"
        when: windowShown
        property var backend
        property var sent
        function init() {
            failOnWarning(/.?/)
            backend = createTemporaryObject(bridgeComponent, parent)
            backend.connected = true
            sent = []
            backend.send.connect(function(message) { sent.push(JSON.parse(message)) })
            rows.clear()
        }
        function reply(result, error) {
            var request = sent[sent.length - 1]
            backend.receive(JSON.stringify({version: 1, id: request.id, result: result, error: error}))
        }
        function job(id, state, created) {
            return {id: id, state: state, created: created, browser: "none", progress: 30, size: 100}
        }
        function test_duplicate_click_submits_once_until_ack() {
            verify(backend.request("activity.reopen", {id: "document"}))
            verify(!backend.request("activity.reopen", {id: "document"}))
            compare(sent.length, 1)
            verify(backend.isBusy("activity.reopen", "document"))
            reply({browser: "opened"})
            verify(!backend.isBusy("activity.reopen", "document"))
            verify(backend.request("activity.reopen", {id: "document"}))
        }
        function test_unrelated_actions_have_independent_busy_state() {
            verify(backend.request("settings.set", {key: "recent_limit", value: 20}))
            verify(backend.isBusy("settings.set", "recent_limit"))
            verify(!backend.isBusy("settings.set", "recent_days"))
            verify(backend.request("settings.set", {key: "recent_days", value: 5}))
            compare(sent.length, 2)
        }
        function test_failure_clears_busy_without_success_toast() {
            backend.request("accounts.rename", {id: "account", label: "New label"})
            reply(null, {code: "keyring", message: "ignored"})
            verify(!backend.isBusy("accounts.rename", "account"))
            compare(backend.notice, "")
            verify(backend.error.indexOf("keyring") >= 0)
        }
        function test_success_feedback_waits_for_ack() {
            backend.request("settings.set", {key: "choose_account", value: true})
            compare(backend.notice, "")
            reply({choose_account: true})
            compare(backend.notice, "Settings saved.")
        }
        function test_background_refresh_does_not_clear_action_error() {
            backend.error = "Keep this actionable error"
            backend.request("mime.status", {})
            reply({handlers: [], restoration_pending: false})
            compare(backend.error, "Keep this actionable error")
        }
        function test_import_makes_setup_ready_only_on_success() {
            backend.request("credentials.import", {path: "/tmp/example.json"})
            verify(!backend.snapshot.setup.client_configured)
            reply(null, {code: "invalid_input"})
            verify(!backend.snapshot.setup.client_configured)
            backend.request("credentials.import", {path: "/tmp/example.json"})
            reply({imported: true})
            verify(backend.snapshot.setup.client_configured)
        }
        function test_disconnected_actions_are_not_queued() {
            backend.connected = false
            verify(!backend.request("activity.reopen", {id: "document"}))
            compare(sent.length, 0)
            verify(backend.error.length > 0)
        }
        function test_uploaded_browser_failure_stays_uploaded() {
            var record = job("a", "complete", 1)
            record.browser = "failed"
            verify(Logic.needsAttention(record))
            compare(Logic.stateLabel(record), "Uploaded · browser could not open")
            record.browser = "opened"
            verify(!Logic.needsAttention(record))
        }
        function test_filter_order_stays_stable_when_progress_changes() {
            var a = job("a", "uploading", 2), b = job("b", "complete", 1)
            compare(Logic.visibleJobs([b, a], "all", 50)[0].id, "a")
            a.state = "complete"
            compare(Logic.visibleJobs([b, a], "all", 50)[0].id, "a")
            compare(Logic.visibleJobs([b, a], "attention", 50).length, 0)
        }
        function test_model_updates_preserve_delegate_identity() {
            var a = job("a", "uploading", 2), b = job("b", "complete", 1)
            Logic.syncRows(rows, [a, b])
            rows.setProperty(0, "interaction", "typed input")
            a.progress = 60
            Logic.syncRows(rows, [a, b])
            compare(rows.get(0).interaction, "typed input")
            compare(rows.get(0).record.progress, 60)
            Logic.syncRows(rows, [b, a])
            compare(rows.get(1).interaction, "typed input")
            Logic.syncRows(rows, [a])
            compare(rows.count, 1)
            compare(rows.get(0).key, "a")
        }
        function test_progress_and_relative_times_are_bounded() {
            compare(Logic.progress({size: 100, progress: 150}), 1)
            compare(Logic.progress({size: 0, progress: 150}), 0)
            compare(Logic.relativeTime(2000, 1000000), "Just now")
        }
    }
}
