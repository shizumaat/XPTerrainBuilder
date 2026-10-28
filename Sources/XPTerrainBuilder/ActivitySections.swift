import SwiftUI
import SceneryKit

/// The Build pane's two run sections (#1556) as one native list (#1537,
/// RULINGS 2026-10-28n): Activity — live, failed and stopped rows, the run
/// clock under them — then Completed, the built tiles, its section
/// collapsed to its count ("Completed (12)") until the user opens it onto
/// the compact rows (#1542); the choice holds for the session
/// (`BuildActivityModel.completedExpanded`). A completed tile queued again
/// moves back to Activity. The list's own selection is the map's tile
/// selection (`ActivityListSelection`), drawn by the system; rows take the
/// list's standard insets. Qt twin: `O4_Qt_Activity_List`.
struct ActivitySections: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel
    @EnvironmentObject var controller: AnalysisController

    static func completedTitle(_ count: Int) -> String { "Completed (\(count))" }

    /// Whether the pane shows the list at all: a run, or rows left over.
    static func shows(building: Bool, activity: BuildActivityModel) -> Bool {
        building || !activity.displayOrder.isEmpty
    }

    var body: some View {
        let live = activity.rows(in: .activity)
        let completed = activity.rows(in: .completed)
        List(selection: selection) {
            if buildModel.isBuilding || !live.isEmpty {
                Section {
                    ForEach(live, id: \.self) { coord in
                        ActivityRow(coord: coord, compact: false).tag(coord)
                    }
                } header: {
                    Text("Activity")
                } footer: {
                    runClock
                }
            }
            if !completed.isEmpty {
                Section(isExpanded: $activity.completedExpanded) {
                    ForEach(completed, id: \.self) { coord in
                        ActivityRow(coord: coord, compact: true).tag(coord)
                    }
                } header: {
                    Text(Self.completedTitle(completed.count))
                }
            }
        }
        .listStyle(.sidebar)
    }

    private var selection: Binding<Set<BuildModel.TileCoord>> {
        ActivityListSelection.binding(
            rows: { activity.displayOrder },
            selected: $buildModel.selected,
            active: $buildModel.activeTile,
            frame: { controller.zoomToTile(lat: $0.lat, lon: $0.lon) })
    }

    /// The run's count and clock. It belongs to a run: once one has ended
    /// and only stopped rows are left waiting for a resume, there is no
    /// elapsed to report.
    @ViewBuilder
    private var runClock: some View {
        if buildModel.isBuilding || activity.totalTiles > 0 {
            VStack(alignment: .leading) {
                if activity.totalTiles > 0 {
                    Text("Building \(activity.totalTiles) tile\(activity.totalTiles == 1 ? "" : "s") — \(activity.doneTiles) done")
                }
                HStack {
                    Text("Total \(ProgressRowText.clock(activity.elapsedSeconds))")
                    Spacer()
                    Text(activity.remainingUnreliable
                         ? "Remaining: estimating…"
                         : "Remaining ≈ \(activity.remainingSeconds.map(ProgressRowText.clock) ?? "—")")
                }
            }
            .scaledFont(.caption, monospacedDigit: true)
            .foregroundStyle(.secondary)
        }
    }
}
