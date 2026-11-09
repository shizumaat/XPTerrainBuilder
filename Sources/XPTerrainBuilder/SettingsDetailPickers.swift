import SwiftUI
import SceneryKit

/// Settings ▸ General's Detail picker (#1985), under the preset cards:
/// where to add airport detail. It follows the map selection like the
/// cards (#1549) and shows Custom when no choice's keys all hold (Qt:
/// `O4_Qt_Settings.SettingsWindow.airport_detail_combo`).
struct AirportDetailPicker: View {
    @EnvironmentObject var buildModel: BuildModel
    private static let customTag = "custom"

    var body: some View {
        let _ = buildModel.tileConfigGeneration
        let current = buildModel.currentAirportDetail()
        Picker(AirportDetail.title, selection: Binding(
            get: { current?.key ?? Self.customTag },
            set: { key in
                guard let choice = AirportDetail.choices.first(where: { $0.key == key })
                else { return }
                buildModel.applyAirportDetail(choice)
            })) {
            if current == nil {
                Text(AirportDetail.customTitle).tag(Self.customTag)
            }
            ForEach(AirportDetail.choices) { choice in
                Text(choice.title).tag(choice.key)
            }
        }
        .help(AirportDetail.summary)
        Text(AirportDetail.summary)
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

/// Settings ▸ Imagery's build zoom (#1242, moved from General by #1985):
/// the default for new tiles, or the selection's (#1549), -1 while the
/// selected tiles disagree (Qt: `SettingsWindow.detail_combo`).
struct ImageryZoomPicker: View {
    @EnvironmentObject var buildModel: BuildModel
    private static let conflictTag = -1

    var body: some View {
        let zoom = buildModel.selectionZoom
        Picker(O4Glossary.term("imagery_detail"), selection: Binding(
            get: { zoom.value ?? Self.conflictTag },
            set: { zl in
                guard zl != Self.conflictTag else { return }
                buildModel.editSelection { buildModel.chooseZoom(zl) }
            })) {
            if zoom.isConflicting {
                Text(SettingsSelection.conflictText).tag(Self.conflictTag)
            }
            ForEach(12...21, id: \.self) { zl in
                Text(O4Glossary.detailChoice(zl)).tag(zl)
            }
        }
        .help("More detail means sharper imagery and much larger downloads: one step (one ZL) ≈ 4× the data. Most sources top out below ZL21 — the map's zoom badge shows each source's ceiling.")
    }
}
