import Foundation
import Security

/// The engine's provider sign-ins, held in the APP's Keychain.
///
/// The Python engine stores provider credentials through the `keyring`
/// package when it runs standalone — but under this app the engine is a
/// separate, ad-hoc-signed binary, so its Keychain items would prompt as
/// "Ortho4XP" and lose their access grants on every rebuild (the ad-hoc
/// signature changes each time). The engine therefore brokers secret
/// operations to the app over the JSON-lines protocol (`SecretRequest`
/// events answered by `secret_response` commands), and this store
/// services them: the items, the permission prompt, and the
/// access-control list all belong to the signed app bundle.
///
/// One generic-password item per (session, account), under a single
/// service name; the account attribute is "<sessionName>/<account>"
/// (session names and accounts never contain "/" ambiguity in practice —
/// session names are simple identifiers like "dgterritorio").
public struct ProviderSecretStore: Sendable {
    public static let service = "XPTerrainBuilder provider sign-ins"

    private let backend: any SecretStoreBackend

    public init(backend: any SecretStoreBackend = KeychainSecretBackend()) {
        self.backend = backend
    }

    public struct StoreError: Error, CustomStringConvertible, Sendable {
        public let operation: String
        public let status: OSStatus
        public var description: String {
            let message = SecCopyErrorMessageString(status, nil) as String?
            return "Keychain \(operation) failed: \(message ?? "OSStatus \(status)")"
        }
    }

    private func keychainAccount(_ sessionName: String, _ account: String) -> String {
        "\(sessionName)/\(account)"
    }

    /// The stored secret, or nil when no item exists.
    public func secret(sessionName: String, account: String) throws -> String? {
        let (status, data) = backend.copy(
            service: Self.service,
            account: keychainAccount(sessionName, account))
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data else {
            throw StoreError(operation: "read", status: status)
        }
        return String(decoding: data, as: UTF8.self)
    }

    /// Create or replace the secret for (session, account).
    public func store(sessionName: String, account: String, secret: String) throws {
        let item = keychainAccount(sessionName, account)
        let data = Data(secret.utf8)
        var status = backend.add(
            service: Self.service, account: item,
            label: "XPTerrainBuilder provider sign-in (\(sessionName))",
            secret: data)
        if status == errSecDuplicateItem {
            status = backend.update(service: Self.service, account: item, secret: data)
        }
        guard status == errSecSuccess else {
            throw StoreError(operation: "write", status: status)
        }
    }

    /// Remove the secret; deleting a missing item is not an error.
    public func delete(sessionName: String, account: String) throws {
        let status = backend.delete(
            service: Self.service,
            account: keychainAccount(sessionName, account))
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw StoreError(operation: "delete", status: status)
        }
    }
}

/// The four Security-framework operations the store needs, as a seam so
/// tests run against an in-memory fake instead of the user's Keychain.
public protocol SecretStoreBackend: Sendable {
    func add(service: String, account: String, label: String, secret: Data) -> OSStatus
    func update(service: String, account: String, secret: Data) -> OSStatus
    func copy(service: String, account: String) -> (OSStatus, Data?)
    func delete(service: String, account: String) -> OSStatus
}

/// The live backend: generic-password items in the default Keychain.
public struct KeychainSecretBackend: SecretStoreBackend {
    public init() {}

    private func baseQuery(service: String, account: String) -> [CFString: Any] {
        [kSecClass: kSecClassGenericPassword,
         kSecAttrService: service,
         kSecAttrAccount: account]
    }

    public func add(service: String, account: String, label: String,
                    secret: Data) -> OSStatus {
        var attributes = baseQuery(service: service, account: account)
        attributes[kSecAttrLabel] = label
        attributes[kSecValueData] = secret
        return SecItemAdd(attributes as CFDictionary, nil)
    }

    public func update(service: String, account: String, secret: Data) -> OSStatus {
        SecItemUpdate(
            baseQuery(service: service, account: account) as CFDictionary,
            [kSecValueData: secret] as CFDictionary)
    }

    public func copy(service: String, account: String) -> (OSStatus, Data?) {
        var query = baseQuery(service: service, account: account)
        query[kSecReturnData] = true
        query[kSecMatchLimit] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        return (status, result as? Data)
    }

    public func delete(service: String, account: String) -> OSStatus {
        SecItemDelete(baseQuery(service: service, account: account) as CFDictionary)
    }
}
