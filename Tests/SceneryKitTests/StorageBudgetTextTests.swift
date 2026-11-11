import Foundation
import Testing
@testable import SceneryKit

/// #2007 / RULINGS 2026-11-11a, 11h (1): the default budget's words (it
/// holds the current install until confirmed) and the
/// "downgrade to fit?" confirmation (the same as `O4_Storage_Text`).
struct StorageBudgetTextTests {
    static func budget(set: Bool) throws -> O4StorageBudget {
        let json = """
        {"budget_bytes": 255000000000, "budget_set": \(set), "default_bytes": 255000000000,
         "default_base_bytes": 200000000000, "low_water": 0.9, "used_bytes": 300000000000,
         "floor_bytes": 170000000000, "recommended_bytes": 255000000000,
         "held_bytes": \(set ? 0 : 300000000000),
         "under_floor": false, "over_budget": true}
        """
        return try JSONDecoder().decode(O4StorageBudget.self, from: Data(json.utf8))
    }

    @Test func theDefaultShowsAndAsksBeforeClearing() throws {
        let unset = try Self.budget(set: false)
        #expect(O4StorageText.budgetLines(unset).line.contains("of the default 255.00 GB"))
        #expect(O4StorageText.defaultLine(unset) == "Default 200.00 GB · recommended 255.00 GB")
        #expect(O4StorageText.heldLine(unset).contains("installed now (300.00 GB)"))
        #expect(O4StorageText.heldLine(try Self.budget(set: true)).isEmpty)
    }

    @Test func aLowerBudgetNamesTheBytesAndTheFloor() throws {
        let b = try Self.budget(set: true)
        #expect(O4StorageText.needsDowngrade(b, 150_000_000_000))
        #expect(!O4StorageText.needsDowngrade(b, 400_000_000_000))
        let text = O4StorageText.downgradeMessage(b, 150_000_000_000)
        #expect(text.contains("about 165.00 GB is cleared"))
        #expect(text.contains("your tiles need 170.00 GB"))
    }
}
