import SwiftUI

/// An Activity row's progress bar (owner 2026-11-18, on 1.0.558: "the
/// selected cell progress bar is still not right, almost invisible").
/// On a selected row in the focused list the row is filled with the
/// accent colour, and the system bar ignores `.tint` there: its track and
/// fill both come out accent on accent. So the emphasized row draws its
/// own bar in the same frame — a white fill on a dark translucent track,
/// the selected-row style of `SelectedRowStyle` (#2139). Elsewhere it is
/// the system bar, tinted. Qt twin: `O4_Qt_Activity_Delegate` paints the
/// same on its selected rows.
struct ActivityProgressBar: View {
    let fraction: Double
    let tint: Color
    @Environment(\.backgroundProminence) private var prominence

    /// The emphasized bar's colours: what reads on any accent colour.
    static let emphasizedFill = Color.white
    static let emphasizedTrack = Color.black.opacity(0.28)

    var body: some View {
        let value = min(max(fraction, 0), 1)
        if SelectedRowStyle.isEmphasized(prominence) {
            // The system bar keeps the row's layout; drawn over, hidden.
            ProgressView(value: value, total: 1)
                .controlSize(.small)
                .opacity(0)
                .overlay {
                    GeometryReader { geo in
                        let height = min(geo.size.height, 4)
                        ZStack(alignment: .leading) {
                            Capsule().fill(Self.emphasizedTrack)
                            Capsule().fill(Self.emphasizedFill)
                                .frame(width: geo.size.width * value)
                        }
                        .frame(height: height)
                        .frame(maxHeight: .infinity)
                    }
                }
        } else {
            ProgressView(value: value, total: 1)
                .controlSize(.small)
                .tint(tint)
        }
    }
}
