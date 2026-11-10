import SwiftUI
import SceneryKit

/// Fly mode's side pane (RULINGS 2026-11-10j/g; spec §4.3, §14; lanes U1,
/// U2): name a flight (X-Plane's saved FMS plans, SimBrief, a plan file,
/// or a departure + arrival), the flight card, the readiness checklist and
/// countdown, the World pack and follow lines, and the in-flight controls.
/// The Qt window's `O4_Qt_Fly_Pane.FlyPane` is the same, row for row
/// (`Ortho4XP/tests/test_qt_layout_parity.py` `FLY_PANE`).
struct FlyPane: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        FlyPaneRows(fly: buildModel.fly, follow: buildModel.imageryFollow)
    }
}

private struct FlyPaneRows: View {
    @ObservedObject var fly: FlyModel
    let follow: ImageryFollowModel

    var body: some View {
        VStack(spacing: 0) {
            Text(AppMode.fly.title)
                .scaledFont(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if fly.plan == nil && fly.status == nil {
                        Text(AppModeText.flyPlaceholder)
                            .scaledFont(.callout)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Picker(FlyText.planSourceLabel, selection: $fly.source) {
                        Text(FlyText.planChoose).tag("")
                        Text(FlyText.planSimbrief).tag("simbrief")
                        ForEach(fly.plans, id: \.path) { row in
                            Text(FlyText.planRowLabel(row)).tag(row.path)
                        }
                        Text(FlyText.planNone).tag("none")
                    }
                    SimBriefRow(model: fly)
                    Button(FlyText.openPlan) { fly.openPlanFile() }
                    QuickRouteRow(model: fly)
                    FlightCard(model: fly)
                    Toggle(FlyText.buildAlternate, isOn: $fly.buildAlternate)
                        .disabled(fly.plan?.alternate == nil)
                    CruiseSpeedField(model: fly)
                    CorridorWidthField(model: fly)
                    ReadinessChecklist(model: fly)
                    FlightCountdown(model: fly)
                    WorldStatusLine(model: fly)
                    ImageryFollowLine(model: follow)
                    Picker(FlyText.simPriorityLabel, selection: $fly.simPriority) {
                        ForEach(FlyText.simPriorities, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    Toggle(FlyText.livePreview, isOn: $fly.livePreview)
                        .help(FlyText.livePreviewHelp)
                    Button(FlyText.divert) { fly.divert() }
                        .disabled(fly.status == nil)
                    Button(FlyText.endFlight) { fly.endFlight() }
                        .disabled(fly.status == nil)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
            }
        }
    }
}

/// "SimBrief username or pilot ID" and Fetch (the username is the one
/// Build mode's "Select from flight plan…" remembers).
struct SimBriefRow: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        HStack {
            TextField(FlyText.simbriefPlaceholder, text: Binding(
                get: { model.simBriefUser }, set: { model.simBriefUser = $0 }))
            Button(FlyText.simbriefButton) { model.fetchSimBrief() }
                .disabled(model.simBriefUser.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }
}

/// Departure + arrival: a two-airport plan from X-Plane's airport list.
struct QuickRouteRow: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        HStack {
            TextField(FlyText.quickFrom, text: $model.quickFrom)
            TextField(FlyText.quickTo, text: $model.quickTo)
            Button(FlyText.quickButton) { model.useQuickEntry() }
        }
    }
}

/// Origin, destination, alternate, distance and time en route; the map
/// legend; Prepare flight; the last sentence for the user.
struct FlightCard: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        if let plan = model.plan {
            PaneBox {
                ForEach(FlyText.cardLines(plan, cruise: Double(model.cruiseKt)), id: \.self) {
                    Text($0).scaledFont(.callout)
                }
                FlyLegend()
                Button(FlyText.prepare) { model.prepare() }
            } label: { EmptyView() }
        }
        if let message = model.message {
            Text(message)
                .scaledFont(.caption)
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// The map legend in Fly mode (§14's words).
struct FlyLegend: View {
    var body: some View {
        HStack(spacing: 10) {
            ForEach(FlyText.legend, id: \.0) { key, words in
                HStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(FlyMapOverlay.color(key), lineWidth: 2)
                        .frame(width: 12, height: 12)
                    Text(words).scaledFont(.caption2).foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct CruiseSpeedField: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        LabeledContent(FlyText.cruiseLabel) {
            TextField("", value: $model.cruiseKt, format: .number).frame(width: 70)
        }
    }
}

struct CorridorWidthField: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        LabeledContent(FlyText.corridorLabel) {
            TextField("", value: $model.corridorKm, format: .number).frame(width: 70)
        }
    }
}

/// §6.2's rows from the flight manager's last `FlightStatus`.
struct ReadinessChecklist: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            if let items = model.status?.items, !items.isEmpty {
                ForEach(items, id: \.key) { Text(FlyText.itemText($0)).scaledFont(.caption) }
            } else {
                Text(FlyText.noStatus).scaledFont(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

/// "Ready in about 12 min" and the flight's state line.
struct FlightCountdown: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        if let status = model.status {
            VStack(alignment: .leading, spacing: 2) {
                Text(FlyText.countdown(status.countdownSeconds)).scaledFont(.headline)
                let line = FlyText.statusLine(status)
                if !line.isEmpty {
                    Text(line).scaledFont(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}

struct WorldStatusLine: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        Text(FlyText.worldLine(model.worldStatus))
            .scaledFont(.caption)
            .foregroundStyle(.secondary)
    }
}
