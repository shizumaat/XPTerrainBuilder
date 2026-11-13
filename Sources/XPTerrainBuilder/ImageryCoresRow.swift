import SwiftUI
import SceneryKit

/// A background airport-core sharpening's row in the Activity list
/// (#2039, `ImageryCoresProgress`): the tile, "Sharpening airport imagery
/// · n of N squares", its bar, and stop while it runs; then done, failed
/// or stopped. Not a build row: no clock, no steps, not selectable. Qt
/// twin: `O4_Qt_Core_Rows.CoreRow`.
struct ImageryCoresRow: View {
    @EnvironmentObject var buildModel: BuildModel
    let progress: O4ImageryCoresProgress

    var body: some View {
        let text = ProgressRowText(
            tileKey: BuildModel.TileCoord(lat: progress.lat, lon: progress.lon).key, tag: "",
            status: O4OnDemandText.coresRowStatus(progress), clock: nil)
        let tone = ActivityOrder.tone(state: progress.state, label: progress.state, hasIssues: false)
        TileProgressRowLines(
            text: text, statusColor: ActivityRow.color(tone),
            titleDimmed: !progress.running
        ) {
            ProgressView(value: progress.fraction, total: 1)
                .controlSize(.small)
                .tint(tone == .live ? Color.accentColor : ActivityRow.color(tone))
        } trailing: {
            if progress.running {
                Button {
                    buildModel.stopImageryCores(progress)
                } label: {
                    ActivityRow.stopSign
                }
                .buttonStyle(.borderless)
                .controlSize(.small)
                .help(O4OnDemandText.coresRowStopHelp)
            }
        }
    }
}

extension O4ImageryCoresProgress {
    /// The row's identity in the list: its tile.
    var coresRowID: String { "\(lat),\(lon)" }
}
