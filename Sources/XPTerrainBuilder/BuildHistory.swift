import Foundation
import SceneryKit

/// One row of the Build History list (#1226): a built tile, its newest
/// build record (nil for a tile built before logging) and when it was
/// built — the record's end, else the scan's mesh date.
struct BuildHistoryRow: Identifiable {
    let coord: BuildModel.TileCoord
    let record: TileBuildRecord?
    let date: Double?
    let builtBy: String

    var id: BuildModel.TileCoord { coord }

    /// "Built", "Failed"…, or the before-logging note (owner Q139).
    var outcomeText: String {
        record?.outcomeText ?? "Log not saved (built before logging)"
    }

    var outcomeSymbol: String {
        switch record?.outcome {
        case "ok": return "checkmark.circle.fill"
        case "warnings": return "exclamationmark.triangle.fill"
        case "failed": return "xmark.octagon.fill"
        case "stopped": return "stop.circle"
        default: return "doc.badge.ellipsis"
        }
    }
}

/// Per-tile logs and the build history (#1226, owner Q139): the console
/// filter, the saved-log viewer, the history list and the map's date
/// dimming. The engine writes the logs (`O4_Tile_Build_Log`); this reads
/// them. TWIN of the Qt drawer (`O4_Qt_Build_History.py`).
extension BuildModel {
    /// The selected tiles the console is filtered to, sorted.
    var consoleFilterTiles: [TileCoord] {
        console.filterDismissed ? [] : selected.sorted()
    }

    /// Recompute what the console shows from the selection, the chip and
    /// the Saved logs menu. Called whenever one of them changes.
    func syncConsoleView() {
        if let chosen = console.chosenLog,
           let coord = TileMath.parse(chosen.tile).map({ TileCoord(lat: $0.lat, lon: $0.lon) }),
           let info = built[coord] {
            let record = savedLogs(for: coord).first { $0.log == chosen.log }
            var lines = [Self.savedLogHeader(tile: chosen.tile, record: record)]
            lines += Self.logLines(TileBuildLogs.logText(buildDir: info.buildDir, name: chosen.log))
            console.setView(filter: [chosen.tile], saved: lines, live: false)
            return
        }
        let tiles = consoleFilterTiles
        var saved: [String] = []
        for coord in tiles where !console.hasLiveLines(coord.key) {
            guard let info = built[coord] else { continue }
            guard let record = savedLogs(for: coord).first else {
                saved.append("=== \(coord.key): Log not saved (built before logging) ===")
                continue
            }
            saved.append(Self.savedLogHeader(tile: coord.key, record: record))
            saved += Self.logLines(TileBuildLogs.logText(buildDir: info.buildDir, name: record.log))
        }
        console.setView(filter: Set(tiles.map(\.key)), saved: saved, live: true)
    }

    /// The selection changed: the chip and a picked log no longer apply.
    func selectionChangedForConsole() {
        console.filterDismissed = false
        console.chosenLog = nil
        syncConsoleView()
    }

    /// A tile's kept builds, newest first (read from its build folder).
    func savedLogs(for coord: TileCoord) -> [TileBuildRecord] {
        guard let info = built[coord] else { return [] }
        return TileBuildLogs.records(buildDir: info.buildDir, tile: coord.key)
    }

    /// The Build History list under the date filter, newest first.
    var historyRows: [BuildHistoryRow] {
        built.compactMap { coord, info -> BuildHistoryRow? in
            let date = info.lastBuild?.end ?? info.meshDate
            guard historyRange.contains(date) else { return nil }
            return BuildHistoryRow(coord: coord, record: info.lastBuild, date: date,
                                   builtBy: info.builtBy ?? info.lastBuild?.builtBy ?? "")
        }
        .sorted { ($0.date ?? 0, $1.coord) > ($1.date ?? 0, $0.coord) }
    }

    /// Whether a built tile falls in the date filter (the map dims the
    /// rest).
    func builtInHistoryRange(_ coord: TileCoord) -> Bool {
        guard historyRange != .all, let info = built[coord] else { return true }
        return historyRange.contains(info.lastBuild?.end ?? info.meshDate)
    }

    /// A history row was clicked: select that tile alone, so the console
    /// shows its log.
    func selectFromHistory(_ coord: TileCoord) {
        selected = [coord]
        activeTile = coord
    }

    /// The active tile has no "Built by" yet: ask the engine, which reads
    /// the tile's DSF (never during a scan).
    func refreshBuiltByIfMissing() {
        guard let coord = activeTile, let info = built[coord], info.builtBy == nil,
              info.dsfPresent else { return }
        refreshTileInfo(coord)
    }

    static func savedLogHeader(tile: String, record: TileBuildRecord?) -> String {
        guard let record else { return "=== \(tile): saved log ===" }
        let when = Date(timeIntervalSince1970: record.end)
            .formatted(date: .abbreviated, time: .shortened)
        return "=== \(tile): saved log of the build of \(when) (\(record.outcomeText)) ==="
    }

    private static func logLines(_ text: String) -> [String] {
        var lines = text.components(separatedBy: "\n")
        if lines.last == "" { lines.removeLast() }
        return lines
    }
}
