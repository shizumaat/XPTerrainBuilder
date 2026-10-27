import AppKit
import SwiftUI
import SceneryKit

/// The two text lines of a build-progress row (issue #694). Line one is
/// the title alone, full width, tail-truncated only when it does not fit.
/// Line two is the status, left, and the time, right, then `trailing`
/// (the row's stop / resume button). The status gives way first: it
/// truncates before it reaches the time, which never truncates. Between
/// the bar and line two, the tile's step strip (#825) when it has one.
/// A finished row's title is dimmed (#1341); its status keeps its colour
/// and, when the tile left messages, is a button that reopens them. A
/// built tile's row is compact (#1542): the title, brightened halfway from
/// the dimmed colour to white, then the status line — no bar, no steps.
/// Kept out of `ActivityBox`'s body so the type-checker sees small,
/// explicitly typed expressions.
struct TileProgressRowLines<Bar: View, Trailing: View>: View {
    let text: ProgressRowText
    let statusColor: Color
    var titleDimmed = false
    /// A built tile, in Completed (#1542, #1556): no bar, no steps.
    var compact = false
    /// Non-nil: the status reopens the tile's end-of-build messages.
    var onStatusTap: (() -> Void)?
    /// The row's steps (#825); nil shows none (a legacy-driver build).
    var strip: O4StepStrip?
    /// The progress bar sits right under the title (owner 2026-10-24), so
    /// each bar reads as its tile's when several rows run at once.
    @ViewBuilder let bar: () -> Bar
    @ViewBuilder let trailing: () -> Trailing

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            titleLine
            if !compact {
                bar()
                if let strip {
                    TileStepStrip(strip: strip)
                }
            }
            statusLine
        }
    }

    private var titleLine: some View {
        Text(text.title)
            .scaledFont(.caption, design: .monospaced)
            .lineLimit(1)
            .truncationMode(.tail)
            .foregroundStyle(titleColor)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var titleColor: Color {
        if compact { return Self.completedTitle }
        return titleDimmed ? Color.secondary : Color.primary
    }

    /// A built tile's title (#1542): the dimmed (secondary label) colour
    /// taken 50 % of the way to white, in the current appearance (Qt:
    /// `COMPLETED_TITLE_COLOR`).
    static var completedTitle: Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            var out = NSColor.secondaryLabelColor
            appearance.performAsCurrentDrawingAppearance {
                out = Self.halfwayToWhite(NSColor.secondaryLabelColor)
            }
            return out
        })
    }

    /// `color` 50 % of the way to white (alpha kept).
    static func halfwayToWhite(_ color: NSColor) -> NSColor {
        color.halfway(toward: 1)
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

/// The step strip line of an Activity row (#825): `✓ Map data 0:42 →
/// ● Airports · KSEA — shaping runways (65 %) → ○ Ground …`, each step in
/// its state's colour. The words and states are `O4StepStrip`'s (the
/// mapping both apps share); the Qt half is `O4_Qt_Step_Strip.py`. One
/// wrapping Text: a step's words are joined by no-break spaces, so a
/// narrow row breaks only between steps.
struct TileStepStrip: View {
    let strip: O4StepStrip

    var body: some View {
        Text(Self.attributed(strip))
            .scaledFont(.caption2)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .help(strip.text.replacingOccurrences(of: "\u{00A0}", with: " "))
    }

    static func attributed(_ strip: O4StepStrip) -> AttributedString {
        var out = AttributedString()
        for (index, segment) in strip.segments.enumerated() {
            if index > 0 {
                var separator = AttributedString(O4StepStrip.separator)
                separator.foregroundColor = Color.secondary
                out += separator
            }
            var part = AttributedString(segment.text)
            part.foregroundColor = color(segment.state)
            out += part
        }
        return out
    }

    /// The row's own colours: green done, red failed, orange stopped; the
    /// running step in the accent colour.
    static func color(_ state: O4StepStrip.State) -> Color {
        switch state {
        case .running: return .accentColor
        case .done: return .green
        case .failed: return .red
        case .stopped: return .orange
        case .waiting, .skipped: return .secondary
        }
    }
}
