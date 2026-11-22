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
///
/// CONDENSED (#2190, owner 2026-11-20T01:00Z; an engine with
/// `pack_overlaps_default`): one answer for the whole tile — Prefer the
/// airports / Keep everything — and "Use this for all tiles"; the pairs the
/// answer cannot decide are listed at once, the rest under "Choose by
/// airport…", each picker following the tile's answer until the user picks it.
struct PackOverlapsSheet: View {
    /// Apply's answer: every answerable pair's winner, and the default for
    /// all tiles (nil: not sent — an engine without the capability).
    struct Answer {
        let winners: [String: String]
        let defaultMode: String?
    }

    let offer: O4PackOverlaps
    let condensed: Bool
    /// The answer (Apply), or nil (Not now).
    let answer: (Answer?) -> Void
    /// The user's own picks (a stored answer the tile's answer would change
    /// starts here).
    @State private var picked: [String: String]
    @State private var mode: String
    @State private var allTiles: Bool
    @State private var expanded: Bool

    init(offer: O4PackOverlaps, condensed: Bool, answer: @escaping (Answer?) -> Void) {
        self.offer = offer
        self.condensed = condensed
        self.answer = answer
        let mode = offer.initialMode
        var kept: [String: String] = [:]
        for pair in offer.answerable where !pair.winner.isEmpty
            && pair.winner != pair.winner(for: mode) {
            kept[pair.key] = pair.winner
        }
        _picked = State(initialValue: kept)
        _mode = State(initialValue: mode)
        _allTiles = State(initialValue: !offer.defaultMode.isEmpty)
        _expanded = State(initialValue: !condensed || offer.offers.contains {
            kept[$0.key] != nil && !$0.winner(for: mode).isEmpty
        })
    }

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

    /// The pairs shown: all when expanded, else those the tile's answer
    /// cannot decide.
    private var shown: [O4PackOverlap] {
        expanded ? offer.offers : offer.offers.filter { $0.winner(for: mode).isEmpty }
    }

    /// A pair's picker value: the user's pick, else the tile's answer, else
    /// the remembered answer or the airport pack.
    private func value(_ pair: O4PackOverlap) -> String {
        if let mine = picked[pair.key] { return mine }
        let byMode = condensed ? pair.winner(for: mode) : ""
        return byMode.isEmpty ? pair.preselected : byMode
    }

    @ViewBuilder
    private var tileAnswer: some View {
        Text(O4PackOverlapsCondensedCopy.condensedBody).fixedSize(horizontal: false, vertical: true)
        Picker("", selection: $mode) {
            Text(O4PackOverlapsCondensedCopy.preferLabel).tag(O4PackOverlapsCondensedCopy.prefer)
            Text(O4PackOverlapsCondensedCopy.keepAllLabel).tag(O4PackOverlapsCondensedCopy.keepAll)
        }
        .pickerStyle(.radioGroup)
        .labelsHidden()
        Toggle(O4PackOverlapsCondensedCopy.allTiles, isOn: $allTiles)
            .toggleStyle(.checkbox)
        Text(O4PackOverlapsCondensedCopy.allTilesNote)
            .font(.callout)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        if shown.count < offer.offers.count || expanded {
            DisclosureGroup(O4PackOverlapsCondensedCopy.byAirport, isExpanded: $expanded) {
                EmptyView()
            }
        }
    }

    @ViewBuilder
    private var question: some View {
        if condensed { tileAnswer }
        if expanded {
            Text(O4PackOverlapsCopy.body).fixedSize(horizontal: false, vertical: true)
        } else if !shown.isEmpty {
            Text(O4PackOverlapsCondensedCopy.undecidedNote).fixedSize(horizontal: false, vertical: true)
        }
        if offer.hasSameAirport {
            Text(O4PackOverlapsCopy.sameAirport).fixedSize(horizontal: false, vertical: true)
        }
        if offer.hasDrapes {
            Text(O4PackOverlapsCopy.drapesNote).fixedSize(horizontal: false, vertical: true)
        }
        if shown.count > Self.unscrolledPairs {
            ScrollView { pairList.padding(.trailing, 12) }
                .frame(height: Self.listMaxHeight)
        } else if !shown.isEmpty {
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
                answer(Answer(
                    winners: Dictionary(uniqueKeysWithValues: offer.answerable.map {
                        ($0.key, value($0))
                    }),
                    defaultMode: condensed ? (allTiles ? mode : "") : nil))
            }
            .keyboardShortcut(.defaultAction)
        }
    }

    private var pairList: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(shown) { pair in pairRow(pair) }
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
                    get: { value(pair) },
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
                PackOverlapsSheet(offer: offer,
                                  condensed: buildModel.supportsPackOverlapsDefault) { reply in
                    buildModel.answerPackOverlapsPrompt(reply)
                }
            }
    }
}
