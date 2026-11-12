import SwiftUI
import SceneryKit

/// The imagery follow job as the app sees it (#1992 P4): its last
/// `ImageryFollowStatus`, whether it runs, and whether the user stopped
/// it (then the automatic start leaves it stopped until they follow
/// again). The Qt window's `O4_Qt_Imagery_OnDemand.FollowStatusLine`
/// shows the same.
@MainActor
final class ImageryFollowModel: ObservableObject {
    @Published var status: O4ImageryFollowStatus?
    @Published var running = false
    /// The `imagery_on_demand` world switch, as last read.
    @Published var enabled = false
    var stoppedByUser = false

    /// The line shows while the switch is on or a job runs.
    var shown: Bool { enabled || running || status?.running == true }

    func show(_ status: O4ImageryFollowStatus) {
        self.status = status
        running = status.running
    }
}

/// The Build pane's follow line (spec §7: "Following X-Plane: 14 sharp
/// nearby, 2 downloading, 0 late"): the headline, every other field of
/// the status as its detail, and Follow X-Plane / Stop Following, so a
/// flight needs no Terminal. Words: `O4OnDemandText`.
struct ImageryFollowLine: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: ImageryFollowModel

    var body: some View {
        if model.shown { line }
    }

    private var line: some View {
        let lines = model.status.map(O4OnDemandText.followLines)
        return HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: "airplane")
                .foregroundStyle(model.running ? Color.accentColor : Color.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(O4OnDemandText.followHeadline(model.status, running: model.running))
                    .scaledFont(.caption)
                    .fixedSize(horizontal: false, vertical: true)
                if let detail = lines?.detail {
                    Text(detail)
                        .scaledFont(.caption2)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                let offer = O4OnDemandText.reloadOfferLine(model.status?.reloadOffer ?? "")
                if !offer.isEmpty {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(offer)
                            .scaledFont(.caption)
                            .fixedSize(horizontal: false, vertical: true)
                        Button(O4OnDemandText.reloadSceneryTitle) {
                            buildModel.reloadScenery()
                        }
                        .controlSize(.small)
                    }
                }
            }
            Spacer(minLength: 4)
            Button(model.running ? O4OnDemandText.followStopTitle
                                 : O4OnDemandText.followStartTitle) {
                buildModel.toggleImageryFollow(start: !model.running)
            }
            .controlSize(.small)
        }
        .padding(8)
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 6))
    }
}
