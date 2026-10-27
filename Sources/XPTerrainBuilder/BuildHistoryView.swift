import SwiftUI
import SceneryKit

/// The Build History list beside the console (#1226, owner Q139): every
/// built tile, newest first, narrowed by the one date filter that also
/// dims the map. Clicking a row selects its tile, so the console shows
/// its log. Mirrored by the Qt drawer's history panel
/// (`O4_Qt_Build_History.BuildHistoryPanel`).
struct BuildHistoryView: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Text("Build History")
                    .scaledFont(.subheadline, weight: .semibold)
                Spacer()
                Picker("Built", selection: $buildModel.historyRange) {
                    ForEach(BuildDateRange.allCases) { range in
                        Text(range.label).tag(range)
                    }
                }
                .labelsHidden()
                .fixedSize()
                .help("Show tiles built in this period; the map dims the rest")
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            Divider()
            let rows = buildModel.historyRows
            if rows.isEmpty {
                Text(buildModel.built.isEmpty ? "No built tiles yet."
                     : "No tiles built in this period.")
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
                    .padding(10)
                Spacer()
            } else {
                List(rows) { row in
                    Button {
                        buildModel.selectFromHistory(row.coord)
                    } label: {
                        HistoryRowView(row: row,
                                       selected: buildModel.selected.contains(row.coord))
                    }
                    .buttonStyle(.plain)
                }
                .listStyle(.plain)
            }
        }
    }
}

private struct HistoryRowView: View {
    let row: BuildHistoryRow
    let selected: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: row.outcomeSymbol)
                .foregroundStyle(color)
                .help(row.outcomeText)
            VStack(alignment: .leading, spacing: 1) {
                HStack {
                    Text(row.coord.key)
                        .scaledFont(.caption, weight: selected ? .bold : .semibold,
                                    monospacedDigit: true)
                    Spacer()
                    Text(dateText)
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                }
                Text(detailText)
                    .scaledFont(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .contentShape(Rectangle())
    }

    private var color: Color {
        switch row.record?.outcome {
        case "ok": return .green
        case "warnings": return .yellow
        case "failed": return .red
        default: return .secondary
        }
    }

    private var dateText: String {
        guard let date = row.date, date > 0 else { return "—" }
        return Date(timeIntervalSince1970: date).formatted(date: .abbreviated, time: .shortened)
    }

    /// "Built with warnings · 31 min · XPTerrainBuilder 1.0.430, engine …"
    private var detailText: String {
        var parts = [row.outcomeText]
        if let record = row.record, record.duration > 0 {
            parts.append(Duration.seconds(record.duration)
                .formatted(.units(allowed: [.hours, .minutes, .seconds], width: .abbreviated,
                                  maximumUnitCount: 2)))
        }
        if !row.builtBy.isEmpty { parts.append(row.builtBy) }
        return parts.joined(separator: " · ")
    }
}
