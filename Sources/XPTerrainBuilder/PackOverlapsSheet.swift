import SceneryKit
import SwiftUI

/// The overlapping-packs question (#2145; the Qt window's
/// `O4_Qt_Pack_Overlaps._PackOverlapsBox`, same copy): per pair its
/// summary and a picker (either pack, or Keep both) on the remembered
/// answer, else the airport pack; a same-airport pair (RULINGS 17s) offers
/// to disable the lower pack; a drape pair (RULINGS 19h) offers to hide the
/// lower pack's polygons inside the airport. Apply sends every answerable pair's pick.
/// The tile pane's "Pack choices…" (#2180) opens it on the tile's report:
/// every pair on its stored answer, or "no pairs" and OK.
struct PackOverlapsSheet: View {
    let offer: O4PackOverlaps
    /// `[pair key: winner]` (Apply), or nil (Not now).
    let answer: ([String: String]?) -> Void
    @State private var picked: [String: String] = [:]

    /// A standard size (#2180): the words and buttons always show; the
    /// pairs scroll inside this height, which fits a 13" laptop screen.
    /// The Qt box: `O4_Qt_Pack_Overlaps.LIST_MAX_HEIGHT` / `BOX_WIDTH`.
    static let listMaxHeight: CGFloat = 360
    static let boxWidth: CGFloat = 520
    /// Up to this many pairs fit without scrolling.
    static let unscrolledPairs = 4

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(O4PackOverlapsCopy.title).font(.headline)
            if offer.reportsNone {
                Text(O4PackOverlapsCopy.noPairs).fixedSize(horizontal: false, vertical: true)
                HStack {
                    Spacer()
                    Button(O4PackOverlapsCopy.okButton) { answer(nil) }
                        .keyboardShortcut(.defaultAction)
                }
            } else {
                question
            }
        }
        .padding(20)
        .frame(width: Self.boxWidth)
    }

    @ViewBuilder
    private var question: some View {
        Text(O4PackOverlapsCopy.body).fixedSize(horizontal: false, vertical: true)
        if offer.hasSameAirport {
            Text(O4PackOverlapsCopy.sameAirport).fixedSize(horizontal: false, vertical: true)
        }
        if offer.hasDrapes {
            Text(O4PackOverlapsCopy.drapesNote).fixedSize(horizontal: false, vertical: true)
        }
        if offer.offers.count > Self.unscrolledPairs {
            ScrollView { pairList.padding(.trailing, 12) }
                .frame(height: Self.listMaxHeight)
        } else {
            pairList
        }
        Text(O4PackOverlapsCopy.detail)
            .font(.callout)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        if offer.hasSameAirport {
            Text(O4PackOverlapsCopy.restartNote)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        HStack {
            Spacer()
            Button(O4PackOverlapsCopy.notNowButton, role: .cancel) { answer(nil) }
                .keyboardShortcut(.cancelAction)
            Button(O4PackOverlapsCopy.applyButton) {
                answer(Dictionary(uniqueKeysWithValues: offer.answerable.map {
                    ($0.key, picked[$0.key] ?? $0.preselected)
                }))
            }
            .keyboardShortcut(.defaultAction)
        }
    }

    private var pairList: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(offer.offers) { pair in pairRow(pair) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func pairRow(_ pair: O4PackOverlap) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(pair.summary.isEmpty ? pair.packs.joined(separator: " / ") : pair.summary)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
            if !pair.choices.isEmpty {
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
