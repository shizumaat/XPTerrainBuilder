import SwiftUI
import SceneryKit

/// The two text lines of a build-progress row (issue #694). Line one is
/// the title alone, full width, tail-truncated only when it does not fit.
/// Line two is the status, left, and the time, right, then `trailing`
/// (the row's stop / resume button). The status gives way first: it
/// truncates before it reaches the time, which never truncates.
/// A finished row's title is dimmed (#1341); its status keeps its colour
/// and, when the tile left messages, is a button that reopens them.
/// Kept out of `ActivityBox`'s body so the type-checker sees small,
/// explicitly typed expressions.
struct TileProgressRowLines<Bar: View, Trailing: View>: View {
    let text: ProgressRowText
    let statusColor: Color
    var titleDimmed = false
    /// Non-nil: the status reopens the tile's end-of-build messages.
    var onStatusTap: (() -> Void)?
    /// The progress bar sits right under the title (owner 2026-10-24), so
    /// each bar reads as its tile's when several rows run at once.
    @ViewBuilder let bar: () -> Bar
    @ViewBuilder let trailing: () -> Trailing

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            titleLine
            bar()
            statusLine
        }
    }

    private var titleLine: some View {
        Text(text.title)
            .scaledFont(.caption, design: .monospaced)
            .lineLimit(1)
            .truncationMode(.tail)
            .foregroundStyle(titleDimmed ? Color.secondary : Color.primary)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var statusLine: some View {
        HStack(spacing: 6) {
            status
                .layoutPriority(0)
            Spacer(minLength: 6)
            if let time = text.time {
                Text(time)
                    .scaledFont(.caption, monospacedDigit: true)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .fixedSize()
                    .layoutPriority(1)
            }
            trailing()
        }
    }

    @ViewBuilder
    private var status: some View {
        let label = Text(text.status)
            .underline(onStatusTap != nil)
            .scaledFont(.caption)
            .foregroundStyle(statusColor)
            .lineLimit(1)
            .truncationMode(.tail)
        if let onStatusTap {
            // A button, so the click is the status's own and never also
            // the row's select-and-zoom (#816).
            Button(action: onStatusTap) { label }
                .buttonStyle(.plain)
                .help(O4TileFailureCopy.reopenHelp)
        } else {
            label
        }
    }
}
