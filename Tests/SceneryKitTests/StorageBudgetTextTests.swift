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
         "under_floor": false, "over_budget": true,
         "minimum_bytes": 25000000000, "maximum_bytes": 400000000000,
         "chosen_bytes": 900000000000, "clamped": "followed",
         "breakdown": {"tiles": 200000000000, "other": 100000000000},
         "ladder": {"caches": 20000000000, "imagery": 50000000000, "airport_imagery": 30000000000}}
        """
        return try JSONDecoder().decode(O4StorageBudget.self, from: Data(json.utf8))
    }

    @Test func theDefaultShowsAndAsksBeforeClearing() throws {
        let unset = try Self.budget(set: false)
        #expect(O4StorageText.budgetLines(unset).line.contains("of the default 255.00 GB"))
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

    /// #2022: the slider's ends, notice, bar and preview (the same
    /// sentences `test_storage_text_parity.py` pins for the Qt window).
    @Test func theSliderSaysWhatABudgetClears() throws {
        let b = try Self.budget(set: true)
        #expect(O4StorageText.endLabels(b).min.hasSuffix("airport packages (25.00 GB)"))
        #expect(O4StorageText.endLabels(b).max == "Most: as much as fits while keeping 50 GB free (400.00 GB)")
        #expect(O4StorageText.rangeNotice(b).contains("follows the disk down to 255.00 GB"))
        #expect(O4StorageText.barParts(b)[1].legend == "Tiles and mesh 200.00 GB")
        #expect(O4StorageText.previewText(b, 300_000_000_000) == "Nothing is cleared: the 300.00 GB in use fits.")
        #expect(O4StorageText.previewText(b, 280_000_000_000)
                == "Frees about 48.00 GB: caches go first, then distant imagery goes back to low res. Airports keep full resolution.")
    }
}
