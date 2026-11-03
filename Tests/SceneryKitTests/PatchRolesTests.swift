import Foundation
import Testing
@testable import SceneryKit

/// #1697: the shape's pack pavement, as the engine's `user_roles.source_of`
/// names it, and the `patch_roles` / `patch_role_set` replies.
struct PatchRolesTests {
    @Test func sourceOfRefMatchesTheEngine() {
        #expect(O4PatchRoles.source(ofRef: "pav131") == "pav131")
        #expect(O4PatchRoles.source(ofRef: "pav54#2") == "pav54")
        #expect(O4PatchRoles.source(ofRef: "pav54#plateau:building70") == "pav54")
        #expect(O4PatchRoles.source(ofRef: "dsf:pol267") == "dsf:pol267")
        #expect(O4PatchRoles.source(ofRef: "dsf:objpav3#1") == "dsf:objpav3")
        for ref in ["adjacent_ground", "route8", "pav", "pavx1", "xpav1", "", "dsf:fac2", "dsf:pol"] {
            #expect(O4PatchRoles.source(ofRef: ref) == nil)
        }
        #expect(O4PatchRoles.source(ofRef: nil) == nil)
    }

    @Test func repliesDecode() throws {
        let roles = try JSONDecoder().decode(O4PatchRoles.self, from: Data("""
            {"choices": [{"role": "apron", "label": "Apron"}],
             "overrides": [{"source": "pav7", "role": "apron", "was": "junction",
                            "description": "", "set_at": ""}], "path": "o4_user_roles_ZZZZ.json"}
            """.utf8))
        #expect(roles.override(forRef: "pav7#1")?.was == "junction")
        #expect(roles.override(forRef: "pav8") == nil)
        let set = try JSONDecoder().decode(O4PatchRoleSet.self, from: Data("""
            {"source": "pav7", "role": null, "previous_role": "apron", "description": "", "path": "x"}
            """.utf8))
        #expect(set.role == nil && set.previousRole == "apron")
        #expect(O4ProtocolVersion.supportsPatchRoles("1.33") && !O4ProtocolVersion.supportsPatchRoles("1.32"))
    }
}
