import SwiftUI
import SceneryKit

/// The one sheet a build press shows when airports on the edge of the
/// selected tiles reach into tiles that are not being built (protocol 1.8,
/// spec insets-follow-patch-set-spec.md §C.7, owner RULINGS 2026-09-18i).
///
/// ONE sheet for the whole press, whatever it enqueues: the answer is a
/// POLICY, not a list of ICAOs. The preselected (Return-key) action is the
/// engine's `default_choice`, never a constant here — the two front ends
/// must not spell the default differently.
///
/// COPY (the lead's, final — do not paraphrase): `BoundaryCopy`.
enum BoundaryCopy {
    static let title = "Airports on a tile edge"
    static let body = "These airports extend into tiles you haven't selected. "
        + "To grade a whole airport, the adjacent tiles have to be built too."
    static let skipFootnote = "Skipped airports keep ungraded terrain in this build."
    static let remember = "Remember my choice"
    static let skip = "Skip these airports' patches"
    static let cancel = "Cancel build"

    static func buildAdjacent(_ addTileCount: Int) -> String {
        "Build adjacent tiles too (\(addTileCount))"
    }

    /// "LPMT Montijo — extends 1,240 m into +38-009"
    static func row(_ airport: O4BoundaryAirport) -> String {
        BuildModel.boundaryAirportLines([airport]).first ?? airport.icao
    }
}

struct BoundaryAirportsSheet: View {
    let prompt: BuildModel.BoundaryPrompt
    /// nil = Cancel build.
    let answer: (BuildModel.BoundaryChoice?, Bool) -> Void

    @StateObject private var remember = ViewState(false)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(BoundaryCopy.title).font(.headline)
            Text(BoundaryCopy.body)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(prompt.airports) { airport in
                        Text(BoundaryCopy.row(airport))
                            .font(.callout.monospacedDigit())
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 180)
            Text(BoundaryCopy.skipFootnote)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Toggle(BoundaryCopy.remember, isOn: $remember.value)
                .toggleStyle(.checkbox)
            HStack {
                Button(BoundaryCopy.cancel) { answer(nil, false) }
                    .keyboardShortcut(.cancelAction)
                Spacer()
                Button(BoundaryCopy.skip) {
                    answer(.skip, remember.value)
                }
                .modifier(DefaultActionIf(prompt.defaultChoice == .skip))
                Button(BoundaryCopy.buildAdjacent(prompt.addTiles.count)) {
                    answer(.neighbour, remember.value)
                }
                .buttonStyle(.borderedProminent)
                .modifier(DefaultActionIf(prompt.defaultChoice == .neighbour))
            }
        }
        .padding(20)
        .frame(width: 460)
    }
}

/// The Return key goes to whichever button the ENGINE preselected.
private struct DefaultActionIf: ViewModifier {
    let isDefault: Bool

    init(_ isDefault: Bool) { self.isDefault = isDefault }

    func body(content: Content) -> some View {
        if isDefault {
            content.keyboardShortcut(.defaultAction)
        } else {
            content
        }
    }
}
