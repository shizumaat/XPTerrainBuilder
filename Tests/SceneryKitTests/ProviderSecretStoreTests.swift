import Testing
import Foundation
import Security
@testable import SceneryKit

/// In-memory stand-in for the Keychain, mimicking SecItem semantics:
/// add fails on duplicates, update/copy/delete report not-found.
private final class FakeBackend: SecretStoreBackend, @unchecked Sendable {
    var items: [String: Data] = [:]
    var forcedStatus: OSStatus?
    var log: [String] = []

    func add(service: String, account: String, label: String, secret: Data) -> OSStatus {
        log.append("add \(service)|\(account)|\(label)")
        if let forcedStatus { return forcedStatus }
        if items[account] != nil { return errSecDuplicateItem }
        items[account] = secret
        return errSecSuccess
    }

    func update(service: String, account: String, secret: Data) -> OSStatus {
        log.append("update \(service)|\(account)")
        if let forcedStatus { return forcedStatus }
        guard items[account] != nil else { return errSecItemNotFound }
        items[account] = secret
        return errSecSuccess
    }

    func copy(service: String, account: String) -> (OSStatus, Data?) {
        log.append("copy \(service)|\(account)")
        if let forcedStatus { return (forcedStatus, nil) }
        guard let data = items[account] else { return (errSecItemNotFound, nil) }
        return (errSecSuccess, data)
    }

    func delete(service: String, account: String) -> OSStatus {
        log.append("delete \(service)|\(account)")
        if let forcedStatus { return forcedStatus }
        guard items.removeValue(forKey: account) != nil else { return errSecItemNotFound }
        return errSecSuccess
    }
}

@Suite struct ProviderSecretStoreTests {

    @Test func storeAndReadBack() throws {
        let backend = FakeBackend()
        let store = ProviderSecretStore(backend: backend)
        try store.store(sessionName: "dgterritorio", account: "user@example.org",
                        secret: "hunter2")
        // Keyed by "<session>/<account>" under the app's one service name.
        #expect(backend.items["dgterritorio/user@example.org"] == Data("hunter2".utf8))
        #expect(backend.log.first?.contains(ProviderSecretStore.service) == true)
        let value = try store.secret(sessionName: "dgterritorio",
                                     account: "user@example.org")
        #expect(value == "hunter2")
    }

    @Test func storeReplacesExistingViaUpdate() throws {
        let backend = FakeBackend()
        let store = ProviderSecretStore(backend: backend)
        try store.store(sessionName: "s", account: "u", secret: "old")
        try store.store(sessionName: "s", account: "u", secret: "new")
        #expect(backend.items["s/u"] == Data("new".utf8))
        #expect(backend.log.contains { $0.hasPrefix("update ") })
        #expect(try store.secret(sessionName: "s", account: "u") == "new")
    }

    @Test func missingItemReadsAsNil() throws {
        let store = ProviderSecretStore(backend: FakeBackend())
        #expect(try store.secret(sessionName: "s", account: "nobody") == nil)
    }

    @Test func deleteIsIdempotent() throws {
        let backend = FakeBackend()
        let store = ProviderSecretStore(backend: backend)
        try store.store(sessionName: "s", account: "u", secret: "pw")
        try store.delete(sessionName: "s", account: "u")
        #expect(backend.items.isEmpty)
        // Deleting again (not found) is not an error.
        try store.delete(sessionName: "s", account: "u")
    }

    @Test func hardFailuresThrowWithStatus() {
        let backend = FakeBackend()
        backend.forcedStatus = errSecInteractionNotAllowed
        let store = ProviderSecretStore(backend: backend)
        #expect(throws: ProviderSecretStore.StoreError.self) {
            _ = try store.secret(sessionName: "s", account: "u")
        }
        #expect(throws: ProviderSecretStore.StoreError.self) {
            try store.store(sessionName: "s", account: "u", secret: "pw")
        }
        #expect(throws: ProviderSecretStore.StoreError.self) {
            try store.delete(sessionName: "s", account: "u")
        }
    }

    /// Wire format from the engine's protocol tests
    /// (Ortho4XP/tests/test_secret_broker.py).
    @Test func secretRequestEventParsing() {
        let object = (try? JSONSerialization.jsonObject(with: Data(
            #"{"event":"SecretRequest","request_id":3,"operation":"get","session_name":"dgterritorio","account":"user@example.org","secret":"","seq":2,"ts":1.0}"#
                .utf8))) as? [String: Any]
        let event = object.flatMap { O4Event.parse(object: $0) }
        #expect(event == .secretRequest(requestID: 3, operation: "get",
                                        sessionName: "dgterritorio",
                                        account: "user@example.org", secret: ""))
    }
}
