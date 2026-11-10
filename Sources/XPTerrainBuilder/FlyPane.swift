import SwiftUI
import SceneryKit

/// Fly mode's side pane (RULINGS 2026-11-10j; spec §14, lane U1): a
/// placeholder until the flight manager lands (lanes F1b/U2), and the
/// imagery follow line, moved here from the Build pane. The Qt window's
/// `O4_Qt_Modes.FlyPane` is the same.
struct FlyPane: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        VStack(spacing: 0) {
            Text(AppMode.fly.title)
                .scaledFont(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(AppModeText.flyPlaceholder)
                        .scaledFont(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    // Imagery on demand (#1992 §7; the Qt window's
                    // FollowStatusLine): while the switch is on or the
                    // follow job runs.
                    ImageryFollowLine(model: buildModel.imageryFollow)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
            }
        }
    }
}
