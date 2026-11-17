import SceneryKit
import SwiftUI

/// The overlapping-packs question (#2145; the Qt window's
/// `O4_Qt_Pack_Overlaps._PackOverlapsBox`, same copy): per pair its
/// summary and a picker (either pack, or Keep both) on the remembered
/// answer, else the airport pack. Apply sends every pair's pick.
struct PackOverlapsSheet: View {
    let offer: O4PackOverlaps
    /// `[pair key: winner]` (Apply), or nil (Not now).
    let answer: ([String: String]?) -> Void
    @State private var picked: [String: String] = [:]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(O4PackOverlapsCopy.title).font(.headline)
            Text(O4PackOverlapsCopy.body).fixedSize(horizontal: false, vertical: true)
            ForEach(offer.offers) { pair in
                VStack(alignment: .leading, spacing: 4) {
                    Text(pair.summary.isEmpty ? pair.packs.joined(separator: " / ") : pair.summary)
                        .font(.callout)
                        .fixedSize(horizontal: false, vertical: true)
                    Picker("", selection: Binding(
                        get: { picked[pair.key] ?? pair.preselected },
                        set: { picked[pair.key] = $0 })) {
                        ForEach(pair.choices, id: \.winner) { choice in
                            Text(choice.label).tag(choice.winner)
                        }
                    }
                    .labelsHidden()
                }
            }
            Text(O4PackOverlapsCopy.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(O4PackOverlapsCopy.notNowButton, role: .cancel) { answer(nil) }
                    .keyboardShortcut(.cancelAction)
                Button(O4PackOverlapsCopy.applyButton) {
                    answer(Dictionary(uniqueKeysWithValues: offer.offers.map {
                        ($0.key, picked[$0.key] ?? $0.preselected)
                    }))
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 520)
    }
}

/// The overlapping-packs question on the map window (#2145). A modifier of
/// its own so `MapMainView.body` stays within the compiler's type-check
/// budget.
struct PackOverlapsPrompt: ViewModifier {
    @ObservedObject var buildModel: BuildModel

    func body(content: Content) -> some View {
        content
            .sheet(item: Binding(
                get: { buildModel.packOverlapsPrompt },
                set: { _ in }
            )) { offer in
                PackOverlapsSheet(offer: offer) { winners in
                    buildModel.answerPackOverlapsPrompt(winners: winners)
                }
            }
    }
}
