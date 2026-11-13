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

    /// A row's identity in the list is its tile AND its section (#1736): a
    /// tile that changes section leaves one and enters the other, never
    /// "moves" with its old identity — the outline the sidebar list draws
    /// can then never keep showing a row in the section it left. The
    /// selection stays keyed by tile (`.tag`).
    struct RowID: Hashable, Identifiable {
        let section: ActivityOrder.Section
        let coord: BuildModel.TileCoord
        var id: Self { self }
    }

    static func rowIDs(_ coords: [BuildModel.TileCoord],
                       in section: ActivityOrder.Section) -> [RowID] {
        coords.map { RowID(section: section, coord: $0) }
    }

    /// The core rows' sections (#2052): running ones in Activity, finished
    /// ones (done, failed, stopped) in Completed. Qt: `place_cores`.
    static func coreSections(_ rows: [O4ImageryCoresProgress])
        -> (live: [O4ImageryCoresProgress], done: [O4ImageryCoresProgress]) {
        (rows.filter(\.running), rows.filter { !$0.running })
    }

    /// Whether the pane shows the list at all: a run, or rows left over.
    static func shows(building: Bool, activity: BuildActivityModel) -> Bool {
        building || !activity.displayOrder.isEmpty || !activity.coreRows.isEmpty
    }

    var body: some View {
        let live = activity.rows(in: .activity)
        let completed = activity.rows(in: .completed)
        // Background core sharpenings (#2039): a running one in Activity,
        // a finished one in Completed (#2052), so the queue shows only
        // live work. Not selectable.
        let (liveCores, doneCores) = Self.coreSections(activity.coreRows)
        List(selection: selection) {
            if buildModel.isBuilding || !live.isEmpty || !liveCores.isEmpty {
                Section {
                    ForEach(Self.rowIDs(live, in: .activity)) { row in
                        ActivityRow(coord: row.coord, compact: false).tag(row.coord)
                    }
                    ForEach(liveCores, id: \.coresRowID) { progress in
                        ImageryCoresRow(progress: progress)
                    }
                } header: {
                    Text("Activity")
                } footer: {
                    runClock
                }
            }
            if !completed.isEmpty || !doneCores.isEmpty {
                Section(isExpanded: $activity.completedExpanded) {
                    ForEach(Self.rowIDs(completed, in: .completed)) { row in
                        ActivityRow(coord: row.coord, compact: true).tag(row.coord)
                    }
                    ForEach(doneCores, id: \.coresRowID) { progress in
                        ImageryCoresRow(progress: progress)
                    }
                } header: {
                    Text(Self.completedTitle(completed.count + doneCores.count))
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
