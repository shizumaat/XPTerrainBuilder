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
    public static let budgetUnset = "No disk budget set: using {used}. Recommended at least {recommended} ({floor} is never cleared)."
    public static let budgetUnderFloor = "The budget is below what is never cleared ({floor}). Raise it to at least {recommended}."
    public static let budgetHelp = "Never cleared: your built tiles' scenery files and low-res imagery, your airport patches and your own elevation files. The recommended minimum adds room to work: half of that, at least 50 GB. Over the budget, what is cheapest to rebuild goes first, oldest first; favorites go last."
    public static let ondemandFloorWarning = "Your on-demand tiles need {floor} even at low resolution, more than the {cap} limit."
    public static let installedTitle = "Installed ortho tiles"
    public static let installedLocal = "{count} folder(s) on this disk: {bytes}"
    public static let installedLinked = "{count} linked to {volume}{unmounted}, not measured"
    public static let installedUnmounted = " (not connected)"
    public static let installedNone = "Set the Custom Scenery folder to measure them."
    public static let installedHelp = "The zOrtho4XP_ entries of X-Plane's Custom Scenery folder. Folders on this disk are measured; entries linked to another drive are counted, not measured."

    static func fill(_ template: String, _ values: [String: String]) -> String {
        O4OnDemandText.fill(template, values)
    }

    /// `(line, warning)` of the scan's budget (warning "" unless under the floor).
    public static func budgetLines(_ b: O4StorageBudget) -> (line: String, warning: String) {
        let size = O4OnDemandText.sizeText
        let values = ["used": size(b.usedBytes), "budget": size(b.budgetBytes),
                      "floor": size(b.floorBytes), "recommended": size(b.recommendedBytes)]
        return (fill(b.budgetBytes > 0 ? budgetLine : budgetUnset, values),
                b.underFloor ? fill(budgetUnderFloor, values) : "")
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
