import SwiftUI
import SceneryKit

/// One per-tile row of the Activity list (`ActivitySections`), like the Qt
/// row: tile key · status · progress bar · per-tile stop (resume, once
/// stopped). Finished rows stay until the app quits, titles dimmed
/// (#1341); built tiles' rows sit in Completed, compact (#1542). Selecting
/// the row is the list's own (#1537); its buttons keep their own actions.
struct ActivityRow: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel
    let coord: BuildModel.TileCoord
    /// A built tile, in Completed (#1542): no bar, no steps.
    let compact: Bool

    /// Point size of the per-tile stop / resume glyphs. Shared so the two
    /// buttons stay the same size as each other beside the row's small text.
    /// 16 pt, not the default caption size: at the shipped size the octagon
    /// was too small to read AS a stop sign (owner, on 1.0.238).
    static let stopIconSize: CGFloat = 16

    var body: some View {
        let progress = activity.tiles[coord]
            ?? TileProgress(state: .queued, label: "queued", percent: 0)
        let text = ProgressRowText(
            tileKey: coord.key, tag: activity.runTags[coord] ?? "",
            status: progress.state == .active
                ? "\(progress.label) · \(Int(progress.percent))%" : progress.label,
            clock: activity.tileClocks[coord])
        let hasIssues = activity.issues[coord] != nil && BuildActivityModel.isFinished(progress)
        let tone = ActivityOrder.tone(state: progress.state.rawValue, label: progress.label,
                                      hasIssues: hasIssues)
        VStack(alignment: .leading) {
            TileProgressRowLines(
                text: text, statusColor: Self.color(tone),
                titleDimmed: BuildActivityModel.isFinished(progress),
                compact: compact,
                onStatusTap: hasIssues ? { buildModel.reopenIssues(coord) } : nil,
                strip: activity.stepStrips[coord]
            ) {
                ProgressView(value: progress.state == .done ? 100 : progress.percent, total: 100)
                    .controlSize(.small)
                    .tint(tone == .live ? Color.accentColor : Self.color(tone))
            } trailing: {
                // Stop sign / resume. Deliberately NOT gated on isBuilding:
                // a stopped row keeps its resume button after the run ends,
                // so the tile never has to be found on the map again.
                if buildModel.usesProtocol {
                    if progress.state == .queued || progress.state == .active
                        || progress.state == .indeterminate {
                        Button {
                            buildModel.cancelTile(coord)
                        } label: {
                            // The octagon IS the stop-sign shape (owner-confirmed).
                            // The white square is an overlaid SHAPE, not a second
                            // SF Symbol: two symbols in a ZStack align by frame,
                            // but each glyph carries its own internal padding, so
                            // the inner one sat visibly off-centre. An overlay
                            // centres geometrically, so this is centred by
                            // construction — do not go back to a ZStack.
                            Image(systemName: "octagon.fill")
                                .font(.system(size: Self.stopIconSize))
                                .foregroundStyle(.red)
                                .overlay {
                                    RoundedRectangle(cornerRadius: 0.75)
                                        .fill(.white)
                                        .frame(width: Self.stopIconSize * 0.38,
                                               height: Self.stopIconSize * 0.38)
                                }
                        }
                        .buttonStyle(.borderless)
                        .controlSize(.small)
                        .help("Stop this tile")
                    } else if progress.state == .stopped {
                        Button {
                            buildModel.resumeTile(coord)
                        } label: {
                            Image(systemName: "play.circle.fill")
                                .font(.system(size: Self.stopIconSize))
                                .foregroundStyle(.green)
                        }
                        .buttonStyle(.borderless)
                        .controlSize(.small)
                        .help("Resume this tile")
                    }
                }
            }
            // A stopped tile: what the engine left it with (#598).
            if !progress.detail.isEmpty,
               progress.state == .stopped || progress.label == "stopped" {
                Text(progress.detail)
                    .scaledFont(.caption2)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Gold for a tile built with warnings (#1341; Qt's `WARNING_COLOR`).
    static let warningGold = Color(red: 212.0 / 255, green: 160.0 / 255, blue: 23.0 / 255)

    /// A status tone's colour, the same in the Qt window.
    static func color(_ tone: ActivityOrder.Tone) -> Color {
        switch tone {
        case .done: return .green
        case .warning: return warningGold
        case .failed: return .red
        case .stopped: return .orange
        case .live: return .secondary
        }
    }
}
