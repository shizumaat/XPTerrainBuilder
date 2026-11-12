import Foundation

/// The words of Settings ▸ Storage's budget and installed-tiles lines
/// (RULINGS 2026-11-10d; owner feedback on 1.0.480): the mirror of
/// `Ortho4XP/src/O4_Storage_Text.py`, which the Qt window reads.
/// `Ortho4XP/tests/test_storage_text_parity.py` parses the `static let`
/// literals below and requires them to equal the Python constants.
public enum O4StorageText {
    public static let cachesHelp = "Files in the app's own data folder that builds download or rebuild. Tiles installed in X-Plane are not counted here."
    public static let keptHelp = "The built tiles, patches, overlays and elevation files inside the app's own data folder only. Tiles installed elsewhere are in Installed ortho tiles."
    public static let budgetTitle = "Disk budget"
    public static let budgetLine = "Using {used} of {budget}; {floor} is never cleared. Recommended at least {recommended}."
    public static let budgetUnset = "Using {used} of the default {budget}; {floor} is never cleared."
    public static let budgetUnderFloor = "The budget is below what is never cleared ({floor}). Raise it to at least {recommended}."
    public static let budgetHelp = "More space keeps downloads and rebuild data, so tiles rebuild in minutes instead of re-downloading. Never cleared: your built tiles' scenery files and low-res imagery, your airport patches and your own elevation files. The recommended minimum adds room to work: half of that, at least 50 GB. Over the budget, what is cheapest to rebuild goes first, oldest first; favorites go last."
    public static let budgetDefault = "Default {base} · recommended {recommended}"
    public static let budgetField = "Budget (GB)"
    public static let budgetSet = "Set"
    public static let budgetUseDefault = "Use Default"
    public static let budgetHeld = "Until you confirm a budget, the default holds everything installed now ({held}), so nothing is cleared. Confirm it or set your own."
    public static let budgetConfirm = "Confirm"
    public static let downgradeTitle = "Downgrade scenery to low res to fit the new budget?"
    public static let downgradeText = "{used} is in use and the budget is {budget}: about {free} is cleared to fit. Caches go first, then the oldest sharp imagery is made low res (favorites last). Your tiles and patches stay."
    public static let downgradeFloor = " Even at low res your tiles need {floor}, more than this budget."
    public static let downgradeOk = "Downgrade"
    public static let cachesTitle = "Caches"
    public static let cachesClear = "Clear…"
    public static let cachesDetails = "Details…"
    public static let cachesDetailsTitle = "Storage Details"
    public static let clearAllTitle = "Clear every cache?"
    public static let clearAllText = "This frees up to {bytes}. Downloads come back when a build needs them; sharp imagery is made low res, never deleted. Built tiles and patches stay."
    public static let folderTitle = "Data folder"
    public static let ondemandFloorWarning = "Your on-demand tiles need {floor} even at low resolution, more than the {cap} limit."
    public static let installedTitle = "Installed ortho tiles"
    public static let installedLocal = "{count} folder(s) on this disk: {bytes}"
    public static let installedLinked = "{count} linked to {volume}{unmounted}, not measured"
    public static let installedUnmounted = " (not connected)"
    public static let installedNone = "Set the Custom Scenery folder to measure them."
    public static let installedHelp = "The zOrtho4XP_ entries of X-Plane's Custom Scenery folder. Folders on this disk are measured; entries linked to another drive are counted, not measured."

    public static let worldForeign = "Your World folder is a link to {target}, not a folder XPTerrainBuilder made. Remove the link or restore it before converting tiles."
    public static let worldPackMissing = "{count} tiles that Convert existing tiles moved are missing from the World pack (was its folder moved or deleted?). Undo… in Convert existing tiles puts them back in their own packs."

    /// The sentence for a World folder that is not the app's own
    /// (`world_onboard`'s `world_foreign`; the engine refuses Convert with it).
    public static func worldForeignText(_ target: String) -> String {
        fill(worldForeign, ["target": target])
    }

    static func fill(_ template: String, _ values: [String: String]) -> String {
        O4OnDemandText.fill(template, values)
    }

    /// `(line, warning)` of the scan's budget (warning "" unless under the floor).
    public static func budgetLines(_ b: O4StorageBudget) -> (line: String, warning: String) {
        let size = O4OnDemandText.sizeText
        let values = ["used": size(b.usedBytes), "budget": size(b.budgetBytes),
                      "floor": size(b.floorBytes), "recommended": size(b.recommendedBytes)]
        return (fill((b.budgetSet ?? (b.budgetBytes > 0)) ? budgetLine : budgetUnset, values),
                b.underFloor ? fill(budgetUnderFloor, values) : "")
    }

    /// "Default 200 GB · recommended N" (RULINGS 2026-11-11a).
    public static func defaultLine(_ b: O4StorageBudget) -> String {
        fill(budgetDefault, ["base": O4OnDemandText.sizeText(b.defaultBaseBytes ?? 0),
                             "recommended": O4OnDemandText.sizeText(b.recommendedBytes)])
    }

    /// Unconfirmed: the default holds the current install (RULINGS
    /// 2026-11-11h (1)) and the invitation to confirm it; else "".
    public static func heldLine(_ b: O4StorageBudget) -> String {
        guard b.budgetSet == false else { return "" }
        return fill(budgetHeld, ["held": O4OnDemandText.sizeText(b.heldBytes ?? 0)])
    }

    /// A budget of `newBytes` is below what is in use: ask first.
    public static func needsDowngrade(_ b: O4StorageBudget, _ newBytes: Int64) -> Bool {
        newBytes < b.usedBytes
    }

    /// The confirmation of a budget below what is in use, with the bytes a
    /// clearing frees (down to `lowWater` of the budget).
    public static func downgradeMessage(_ b: O4StorageBudget, _ newBytes: Int64) -> String {
        let size = O4OnDemandText.sizeText
        let low = Int64((b.lowWater ?? 0.9) * Double(newBytes))
        var text = fill(downgradeText, ["used": size(b.usedBytes), "budget": size(newBytes),
                                        "free": size(max(0, b.usedBytes - low))])
        if newBytes < b.floorBytes { text += fill(downgradeFloor, ["floor": size(b.floorBytes)]) }
        return text
    }

    /// The Caches line's Clear… confirmation.
    public static func clearAllMessage(_ cacheBytes: Int64) -> String {
        fill(clearAllText, ["bytes": O4OnDemandText.sizeText(cacheBytes)])
    }

    /// The lines of the scan's installed tiles.
    public static func installedLines(_ i: O4InstalledTiles) -> [String] {
        guard i.measured else { return [installedNone] }
        return [fill(installedLocal, ["count": "\(i.localCount)",
                                      "bytes": O4OnDemandText.sizeText(i.localBytes)])]
            + i.linked.map {
                fill(installedLinked, ["count": "\($0.count)", "volume": $0.volume,
                                       "unmounted": $0.mounted ? "" : installedUnmounted])
            }
    }

    /// The warning after an automatic cleanup (run after every build): the
    /// budget under the floor, else the on-demand tiles over the sharp
    /// imagery limit even low-res; "".
    public static func cleanupWarning(_ done: O4StorageCleared) -> String {
        if let budget = done.budget, budget.underFloor { return budgetLines(budget).warning }
        guard let floor = done.ondemandFloor, floor.overAtFloor else { return "" }
        return fill(ondemandFloorWarning, ["floor": O4OnDemandText.sizeText(floor.floorBytes),
                                           "cap": O4OnDemandText.sizeText(floor.capBytes)])
    }

    /// The on-demand row's warning ("" unless its tiles exceed the limit low-res).
    public static func ondemandWarning(_ store: O4StorageStore) -> String {
        guard store.overAtFloor == true else { return "" }
        return fill(ondemandFloorWarning, ["floor": O4OnDemandText.sizeText(store.floorBytes ?? 0),
                                           "cap": O4OnDemandText.sizeText(store.capBytes ?? 0)])
    }
}
