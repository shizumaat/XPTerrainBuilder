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
                    FlyHereBlock(model: fly, follow: follow)
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
                    OfflineWaiverRow(model: fly)
                    FlightCountdown(model: fly)
                    WorldStatusLine(model: fly)
                    ImageryFollowLine(model: follow)
                    Picker(FlyText.simPriorityLabel, selection: $fly.simPriority) {
                        ForEach(FlyText.simPriorities, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    Picker(FlyText.drapePxLabel, selection: $fly.drapePx) {
                        ForEach(FlyText.drapePxChoices, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    PhotoSourcePicker(model: fly)
                    Toggle(FlyText.livePreview, isOn: $fly.livePreview)
                        .help(FlyText.livePreviewHelp)
                    ReloadOfferRow(model: fly)
                    Button(FlyText.divert) { fly.divertShown = true }
                        .disabled(fly.status == nil)
                        .sheet(isPresented: $fly.divertShown) { DivertSheet(model: fly) }
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

/// Origin, destination, alternate, distance and time en route; Prepare
/// flight; the last sentence for the user.
struct FlightCard: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        if let plan = model.plan {
            PaneBox {
                ForEach(FlyText.cardLines(plan, cruise: Double(model.cruiseKt)), id: \.self) {
                    Text($0).scaledFont(.callout)
                }
                Button(FlyText.prepare) { model.prepare() }
                AdoptedChoiceRows(model: model)
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

/// Inside the flight card (#2025): a departure or destination on a mesh
/// this app did not build asks "fly it as it is, or upgrade it first";
/// once answered, the answer. Qt: `O4_Qt_Fly_Pane.choice_box`.
struct AdoptedChoiceRows: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        ForEach(model.status?.choices ?? [], id: \.role) { row in
            VStack(alignment: .leading, spacing: 4) {
                Text(FlyText.choiceQuestion(row)).scaledFont(.caption)
                    .fixedSize(horizontal: false, vertical: true)
                if row.choice.isEmpty {
                    Button(FlyText.choiceKeepLabel(row)) { model.choose(row, "keep") }
                    Button(FlyText.choiceUpgradeLabel(row)) { model.choose(row, "upgrade") }
                }
            }
        }
    }
}

/// "Photo source": the Build pane's imagery list, bound to the global
/// `default_website` (owner 2026-11-12T19:17Z). Qt: `photo_source_combo`.
struct PhotoSourcePicker: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        if let build = model.build {
            Picker(FlyText.photoSourceLabel, selection: $model.photoSource) {
                ForEach(ImageryMenu.sections(ImageryMenu.entries(
                    build.imagerySources, statuses: build.imageryStatus,
                    forMap: false))) { section in
                    Section(section.title) {
                        ForEach(section.entries) { entry in
                            Text(entry.label).tag(entry.code)
                                .disabled(!entry.enabled)
                                .help(entry.tooltip)
                        }
                    }
                }
            }
        }
    }
}

/// With no plan, the aircraft's own tile (#2020, `WorldStatus.here`):
/// "Preparing imagery at ...", the quick photo, the full-detail squares,
/// and "Reload scenery" while the follow line is not offering it.
/// Qt: `FlyPane.here_block`.
struct FlyHereBlock: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: FlyModel
    @ObservedObject var follow: ImageryFollowModel

    var body: some View {
        let lines = model.plan == nil ? FlyText.hereLines(model.here) : []
        if !lines.isEmpty {
            PaneBox {
                ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                    Text(line)
                        .scaledFont(index == 0 ? .callout : .caption)
                        .foregroundStyle(index == 0 ? .primary : .secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                let followOffers = follow.shown && !(follow.status?.reloadOffer ?? "").isEmpty
                let offer = followOffers ? ""
                    : O4OnDemandText.reloadOfferLine(model.here?["reload_offer"]?.stringValue ?? "")
                if !offer.isEmpty {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(offer).scaledFont(.caption)
                            .fixedSize(horizontal: false, vertical: true)
                        Button(O4OnDemandText.reloadSceneryTitle) { buildModel.reloadScenery() }
                            .controlSize(.small)
                    }
                }
            } label: { EmptyView() }
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

/// "N tiles en route need the internet" and "Fly with X-Plane's own
/// scenery there" (RULINGS 2026-11-10k Q3; lane F2).
struct OfflineWaiverRow: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        let line = FlyDivertText.waiverLine(model.status)
        if !line.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text(line).scaledFont(.caption).foregroundStyle(.orange)
                Button(FlyDivertText.waiveOffline) { model.waiveOffline() }
            }
        }
    }
}

/// The offered reload (rule S6 (a) before departure, (b) in the air):
/// "Reload scenery now", the only way it is sent (owner 2026-11-12).
struct ReloadOfferRow: View {
    @ObservedObject var model: FlyModel

    var body: some View {
        let line = FlyDivertText.reloadLine(model.status)
        if !line.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text(line).scaledFont(.callout)
                Button(FlyDivertText.reloadNow) { model.reload() }
            }
        }
    }
}

/// "Divert…": the plan's alternate first, then any airport by search
/// (spec §4.3 step 8; lane F2).
struct DivertSheet: View {
    @ObservedObject var model: FlyModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(FlyDivertText.divertTitle).scaledFont(.headline)
            if model.hasAlternate {
                Button(FlyDivertText.divertAlternate) { model.divert(to: nil) }
            }
            TextField(FlyDivertText.divertSearch, text: $model.divertQuery)
            List(model.divertResults, id: \.ident) { airport in
                Button(FlyDivertText.rowLabel(airport)) { model.divert(to: airport) }
                    .buttonStyle(.plain)
            }
            .frame(minHeight: 180)
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
            }
        }
        .padding(12)
        .frame(width: 360)
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
