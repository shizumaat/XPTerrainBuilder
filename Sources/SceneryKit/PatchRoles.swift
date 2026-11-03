import Foundation

/// `patch_roles` (protocol 1.33, #1697): the pavement roles a shape can be
/// given, with the words both apps show, and the roles set by hand beside
/// the patch (keyed by the pack pavement, `pav131` or `dsf:pol267`).
public struct O4PatchRoles: Decodable, Equatable, Sendable {
    public struct Choice: Decodable, Equatable, Sendable, Hashable {
        public let role: String
        public let label: String
    }

    public struct Override: Decodable, Equatable, Sendable {
        public let source: String
        public let role: String
        /// The role the classifier gave the shape the user changed.
        public let was: String
        public let description: String
    }

    public let choices: [Choice]
    public let overrides: [Override]

    /// The hand-set role of the pavement a way's `ref` belongs to.
    public func override(forRef ref: String?) -> Override? {
        guard let source = Self.source(ofRef: ref) else { return nil }
        return overrides.first { $0.source == source }
    }

    /// The pack pavement id a way's `ref` names (`pav131`, `pav54#2` →
    /// `pav54`, `dsf:pol267`, `dsf:objpav3#1` → `dsf:objpav3`), or nil —
    /// the engine's `user_roles.source_of`.
    public static func source(ofRef ref: String?) -> String? {
        guard let ref else { return nil }
        for prefix in ["pav", "dsf:pol", "dsf:objpav"] where ref.hasPrefix(prefix) {
            let digits = ref.dropFirst(prefix.count).prefix { $0.isNumber }
            guard !digits.isEmpty else { return nil }
            let rest = ref.dropFirst(prefix.count + digits.count)
            guard rest.isEmpty || rest.first == "#" || rest.first == ":" else { return nil }
            return prefix + digits
        }
        return nil
    }
}

/// `patch_role_set` (protocol 1.33, #1697): the role stored, and the one it
/// replaced (what Undo sends back; nil = the classifier's own).
public struct O4PatchRoleSet: Decodable, Equatable, Sendable {
    public let source: String
    public let role: String?
    public let previousRole: String?
    public let description: String

    private enum CodingKeys: String, CodingKey {
        case source, role, previousRole = "previous_role", description
    }
}

extension O4ProtocolVersion {
    /// A pavement's classification set by hand, `patch_roles` /
    /// `patch_role_set` (protocol 1.33, #1697).
    public static func supportsPatchRoles(_ version: String) -> Bool {
        isAtLeast(version, 1, 33)
    }
}
