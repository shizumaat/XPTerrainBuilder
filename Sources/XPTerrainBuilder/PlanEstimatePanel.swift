import SwiftUI
import SceneryKit

/// The Build box's cost panel (issue #820): what the next Build press will
/// download, write to disk and take, as ranges, with a per-tile list behind
/// a disclosure and the engine's disk verdict (a warning line, or Build off
/// with the reason). The Qt window's twin is `O4_Qt_Plan_Estimate.py`; the
/// lines come from `PlanEstimateText`, which spells them as it does.
struct PlanEstimatePanel: View {
    @ObservedObject var buildModel: BuildModel
    @State private var showingTiles = false

    var body: some View {
        if let estimate = buildModel.planEstimate {
            VStack(alignment: .leading, spacing: 4) {
                Text(PlanEstimateText.total(estimate))
                    .scaledFont(.caption)
                    .fixedSize(horizontal: false, vertical: true)
                if !estimate.tiles.isEmpty {
                    DisclosureGroup("Per tile", isExpanded: $showingTiles) {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(estimate.tiles) { row in
                                Text(PlanEstimateText.tile(row))
                                    .scaledFont(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .scaledFont(.caption)
                }
                if let line = estimate.verdictLine {
                    Label(line, systemImage: "exclamationmark.triangle.fill")
                        .scaledFont(.caption)
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        } else if let error = buildModel.planEstimateError {
            Text("No estimate: \(error)")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
