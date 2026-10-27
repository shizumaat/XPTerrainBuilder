import SwiftUI
import SceneryKit

/// The Build box's headline (#818): what airport grading and custom
/// airport object fitting do, what they cost, and a switch for each that
/// changes THIS build only (Settings keeps the defaults). The list comes
/// from the engine's `build_airports` answer; the Qt window's twin is
/// `O4_Qt_Build_Airports.AirportsCard`, held to the same order by
/// `Ortho4XP/tests/test_qt_layout_parity.py`.
struct BuildAirportsCard: View {
    @EnvironmentObject var buildModel: BuildModel
    /// The engine's answer for the selected tiles; nil while asking, or
    /// when the engine predates it.
    let card: O4BuildAirports?
    let isLoading: Bool
    let error: String?
    /// The app's own pack probe, shown when there is no engine answer.
    let fallbackPacks: [String]
    @State private var showingAirports = false
    /// The explanations sit behind a small "i" (owner 2026-10-27): the
    /// card shows the switches and the list, and the "i" the why.
    @State private var showingGradeInfo = false
    @State private var showingFitInfo = false

    static let gradeSentence = "Runways, taxiways and aprons are reshaped to meet FAA (USA) or ICAO slope and smoothness rules, so you don't get bumpy runways or cliffs at the apron edge. Without this, airports drape over the raw elevation data."
    static let fitSentence = "Moves the 3-D buildings, jetways and roads of these custom airports onto the reshaped ground so nothing floats or sinks."
    static let backupNote = "Originals are backed up. Restore a pack from Modified airports in the Selection box."

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 4) {
                    Toggle(O4Glossary.term("grade_airports"), isOn: Binding(
                        get: { buildModel.gradeAirports },
                        set: { buildModel.setGradeAirports($0) }))
                        .help("For this build only. The default is in Settings.")
                    infoButton($showingGradeInfo)
                }
                if showingGradeInfo { caption(Self.gradeSentence) }
                airportList
                Divider()
                HStack(spacing: 4) {
                    Toggle(O4Glossary.term("fit_buildings"), isOn: Binding(
                        get: { buildModel.fitBuildings },
                        set: { buildModel.setFitBuildings($0) }))
                        .disabled(fitDisabledReason != nil)
                        .help(fitDisabledReason ?? "For this build only. The default is in Settings.")
                    infoButton($showingFitInfo)
                }
                if let reason = fitDisabledReason {
                    caption(reason)
                } else if showingFitInfo {
                    caption(Self.fitSentence)
                }
                packList
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(2)
        } label: {
            Label("Airports", systemImage: "airplane")
                .scaledFont(.callout, weight: .semibold)
        }
    }

    private func infoButton(_ shown: Binding<Bool>) -> some View {
        Button {
            shown.wrappedValue.toggle()
        } label: {
            Image(systemName: shown.wrappedValue ? "info.circle.fill" : "info.circle")
        }
        .buttonStyle(.borderless)
        .help(shown.wrappedValue ? "Hide the explanation" : "What does this do?")
    }

    private func caption(_ text: String) -> some View {
        Text(text)
            .scaledFont(.caption)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.leading, 18)
    }

    @ViewBuilder private var airportList: some View {
        if isLoading && card == nil {
            caption("Reading the airports in the selected tiles…")
        } else if let error {
            caption("The airport list could not be read: \(error)")
        } else if let card {
            if card.airports.isEmpty {
                caption("No airport in the selected tiles is graded.")
            } else {
                DisclosureGroup(isExpanded: $showingAirports) {
                    ForEach(card.airports) { airport in
                        airportRow(airport)
                    }
                } label: {
                    Text(totalLine(card))
                        .scaledFont(.caption)
                }
                .padding(.leading, 18)
            }
        }
    }

    private func airportRow(_ airport: O4BuildAirports.Airport) -> some View {
        HStack(spacing: 6) {
            Text(airport.icao).scaledFont(.caption, weight: .semibold)
            Text(airport.name)
                .scaledFont(.caption)
                .lineLimit(1)
                .truncationMode(.tail)
            Spacer(minLength: 4)
            Text(airport.ruleset).scaledFont(.caption).foregroundStyle(.secondary)
            Text(BuildModel.minutesText(airport.estimateSeconds))
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func totalLine(_ card: O4BuildAirports) -> String {
        let count = card.airports.count
        let airports = "\(count) airport\(count == 1 ? "" : "s")"
        guard buildModel.gradeAirports else { return "\(airports) · not graded in this build" }
        return "\(airports) · adds \(BuildModel.minutesText(card.totalSeconds)) to this build"
    }

    @ViewBuilder private var packList: some View {
        if let card, !card.packs.isEmpty {
            ForEach(card.packs) { pack in
                caption("\(pack.name) · \(pack.objects.formatted()) object\(pack.objects == 1 ? "" : "s")")
            }
            caption(Self.backupNote)
        } else if card == nil, !fallbackPacks.isEmpty {
            caption(fallbackPacks.joined(separator: ", "))
            caption(Self.backupNote)
        }
    }

    /// Why fitting has no effect for this build, or nil when it can run.
    private var fitDisabledReason: String? {
        if !buildModel.gradeAirports { return "Needs airport grading on." }
        let packs = card.map { !$0.packs.isEmpty } ?? !fallbackPacks.isEmpty
        return packs ? nil : "No custom airport with its own 3-D objects in these tiles."
    }
}
