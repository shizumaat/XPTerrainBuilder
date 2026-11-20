import Foundation
import SceneryKit
import SwiftUI

/// The pack commands pressed that the engine has not answered yet (#2200,
/// owner 2026-11-20: "an active dialog should take precedence"): Pack
/// choices… and the Modified-airports row buttons show a working state the
/// moment they are pressed, until the answering event (or a refusal)
/// arrives. Its own observable object, so a wait redraws only the rows
/// that read it. The Qt window's twin: `O4_Qt_Pack_Waits.PackWaits`.
@MainActor
final class PackCommandWaits: ObservableObject {
    /// Keys still waiting (`overlapsKey` / `packKey`).
    @Published private(set) var keys: Set<String> = []

    /// The wait of a tile's overlapping-packs question or answer.
    nonisolated static func overlapsKey(lat: Int, lon: Int) -> String {
        "overlaps|" + TileMath.key(lat: lat, lon: lon)
    }

    /// The wait of a pack row's command, keyed by the pack's folder name
    /// (the events name the pack as the engine resolved its path).
    nonisolated static func packKey(_ packPath: String) -> String {
        "pack|" + URL(fileURLWithPath: packPath).standardizedFileURL.lastPathComponent
    }

    func start(_ key: String) { keys.insert(key) }
    func end(_ key: String) { keys.remove(key) }
    func isWaiting(_ key: String) -> Bool { keys.contains(key) }
}

/// The copy of the waits, VERBATIM and identical to the Qt window's
/// (`Ortho4XP/src/O4_Qt_Pack_Waits.py`, whose twin reads this file).
enum PackWaitCopy {
    static let checking = "Checking packs…"
    static func checkingLine(tile: String) -> String {
        "Pack choices: reading the packs on \(tile)…"
    }
    static func applyingLine(tile: String) -> String {
        "Pack choices: applying your answer on \(tile)…"
    }
    static func appliedLine(tile: String, files: Int) -> String {
        files == 0 ? "Pack choices on \(tile): applied (no pack needed rewriting)."
            : "Pack choices on \(tile): applied (\(files) pack DSF\(files == 1 ? "" : "s") rewritten)."
    }
    static func failedLine(tile: String, error: String) -> String {
        "Pack choices on \(tile): could not be applied (\(error))."
    }
    static func refusedLine(reason: String) -> String {
        "The engine refused the pack command: \(reason)"
    }
}

extension BuildModel {
    /// The reply to a command a wait was started for: a refusal (or an
    /// engine that could not take it) ends the wait with its reason on the
    /// console; "started" leaves it for the answering event.
    nonisolated func packCommandReply(_ key: String) -> @Sendable (O4Reply) -> Void {
        { [weak self] reply in
            let status = reply.result?["status"]?.stringValue ?? ""
            guard !reply.ok || status == "refused" else { return }
            let reason = reply.error ?? reply.result?["reason"]?.stringValue ?? status
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.packWaits.end(key)
                self.console.append(PackWaitCopy.refusedLine(reason: reason))
            }
        }
    }

    /// A pack row's command, sent with its working state (#2200).
    func sendPackRowCommand(packPath: String, _ send: (@escaping @Sendable (O4Reply) -> Void) -> Void) {
        connectIfNeeded()
        let key = PackCommandWaits.packKey(packPath)
        packWaits.start(key)
        send(packCommandReply(key))
    }

    /// The overlapping-packs event's part of the waits: the tile's wait
    /// ends, and an answer's outcome is one console line.
    func packOverlapsArrived(_ offer: O4PackOverlaps) {
        packWaits.end(PackCommandWaits.overlapsKey(lat: offer.lat, lon: offer.lon))
        let tile = TileMath.key(lat: offer.lat, lon: offer.lon)
        switch offer.state {
        case "chosen", "undone":
            console.append(PackWaitCopy.appliedLine(tile: tile, files: offer.files.count))
        case "failed":
            console.append(PackWaitCopy.failedLine(tile: tile, error: offer.error))
        default:
            break
        }
    }
}

/// The tile pane's Pack choices… (#2180) with its working state (#2200):
/// a spinner and "Checking packs…" from the press until the question (or
/// an answer's outcome) arrives.
struct PackChoicesButton: View {
    let buildModel: BuildModel
    @ObservedObject var waits: PackCommandWaits
    let tile: BuildModel.TileCoord

    var body: some View {
        HStack(spacing: 6) {
            Button(O4PackOverlapsCopy.reviewButton) { buildModel.reviewPackOverlaps(tile) }
                .controlSize(.small)
                .help(O4PackOverlapsCopy.reviewHelp)
            if waits.isWaiting(PackCommandWaits.overlapsKey(lat: tile.lat, lon: tile.lon)) {
                ProgressView().controlSize(.mini)
                Text(PackWaitCopy.checking)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

/// The overlapping-packs questions, one per tile (#2200): a tile's
/// question on screen is not asked again behind itself, a newer one for a
/// queued tile replaces the older, and Apply answers the tile's queued
/// ones too — so pressing Pack choices… twice, or a build's question
/// arriving after the report, never re-opens the sheet after Apply.
enum PackOverlapsQueue {
    private static func sameTile(_ a: O4PackOverlaps, _ b: O4PackOverlaps) -> Bool {
        a.lat == b.lat && a.lon == b.lon
    }

    /// `(on screen, queue)` once `offer` (a question to ask) arrived.
    static func arrive(_ offer: O4PackOverlaps, onScreen: O4PackOverlaps?,
                       queue: [O4PackOverlaps]) -> (O4PackOverlaps?, [O4PackOverlaps]) {
        guard let shown = onScreen else { return (offer, queue) }
        if sameTile(shown, offer) { return (shown, queue) }
        return (shown, queue.filter { !sameTile($0, offer) } + [offer])
    }

    /// `(on screen, queue)` once the sheet on screen closed (`answered`:
    /// Apply, else Not now).
    static func closed(_ shown: O4PackOverlaps?, answered: Bool,
                       queue: [O4PackOverlaps]) -> (O4PackOverlaps?, [O4PackOverlaps]) {
        var rest = queue
        if answered, let shown { rest.removeAll { sameTile($0, shown) } }
        guard !rest.isEmpty else { return (nil, []) }
        return (rest.removeFirst(), rest)
    }
}
