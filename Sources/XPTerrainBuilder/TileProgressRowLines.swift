import SwiftUI
import SceneryKit

/// The two text lines of a build-progress row (issue #694). Line one is
/// the title alone, full width, tail-truncated only when it does not fit.
/// Line two is the status, left, and the time, right, then `trailing`
/// (the row's stop / resume button). The status gives way first: it
/// truncates before it reaches the time, which never truncates.
/// Kept out of `ActivityBox`'s body so the type-checker sees small,
/// explicitly typed expressions.
struct TileProgressRowLines<Trailing: View>: View {
    let text: ProgressRowText
    let statusColor: Color
    @ViewBuilder let trailing: () -> Trailing

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            titleLine
            statusLine
        }
    }

    private var titleLine: some View {
        Text(text.title)
            .font(.caption.monospaced())
            .lineLimit(1)
            .truncationMode(.tail)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var statusLine: some View {
        HStack(spacing: 6) {
            Text(text.status)
                .font(.caption)
                .foregroundStyle(statusColor)
                .lineLimit(1)
                .truncationMode(.tail)
                .layoutPriority(0)
            Spacer(minLength: 6)
            if let time = text.time {
                Text(time)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .fixedSize()
                    .layoutPriority(1)
            }
            trailing()
        }
    }
}
