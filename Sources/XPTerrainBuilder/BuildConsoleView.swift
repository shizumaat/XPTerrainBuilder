import SwiftUI
import AppKit
import SceneryKit

/// Bottom pane in Build mode: the engine's console output, streamed live.
/// Same slot the results pane occupies in Manage mode.
struct BuildConsoleView: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            ConsoleTextView(console: buildModel.console)
            Divider()
            bottomBar
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Text("Build Console")
                .font(.headline)
            Spacer()
            Button {
                buildModel.console.clear()
            } label: {
                Image(systemName: "trash")
            }
            .buttonStyle(.borderless)
            .help("Clear the console")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    private var bottomBar: some View {
        HStack(spacing: 8) {
            if buildModel.isBuilding {
                ProgressView().controlSize(.small)
                ConsoleStatusText()
                    .environmentObject(buildModel.activity)
            } else if let summary = buildModel.lastRunSummary {
                Text(summary).foregroundStyle(.secondary)
            } else if buildModel.engine == nil {
                Text("Configure the Ortho4XP engine in Settings to start building.")
                    .foregroundStyle(.secondary)
            } else {
                Text("Select tiles on the map, then press Build.")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if buildModel.isBuilding {
                Button(buildModel.isStopping ? "Stopping…" : "■ Stop") {
                    buildModel.stopBuild()
                }
                .disabled(buildModel.isStopping)
            }
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .frame(height: ResultsPane.bottomBarHeight)
        .background(.bar)
    }

    /// Leaf view observing the high-frequency activity model, so progress
    /// ticks re-render only this text.
    struct ConsoleStatusText: View {
        @EnvironmentObject var activity: BuildActivityModel

        var body: some View {
            let remaining = activity.remainingSeconds.map { ActivityBox.clock($0) } ?? "—"
            Text("\(activity.doneTiles)/\(activity.totalTiles) tiles — elapsed \(ActivityBox.clock(activity.elapsedSeconds)) — remaining ≈ \(remaining)")
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }
}

/// Append-only NSTextView console. SwiftUI Text chokes on thousands of
/// streamed lines; here the coordinator pulls whatever lines it hasn't seen
/// (the model bumps `generation` at ~10 Hz) and appends to the text storage.
struct ConsoleTextView: NSViewRepresentable {
    @ObservedObject var console: BuildConsoleModel

    private static let textColor = NSColor(calibratedRed: 0.82, green: 0.86, blue: 0.9, alpha: 1)
    private static let backgroundColor = NSColor(calibratedRed: 0.043, green: 0.051, blue: 0.071, alpha: 1)

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSTextView.scrollableTextView()
        let textView = scroll.documentView as! NSTextView
        textView.isEditable = false
        textView.isRichText = false
        textView.usesFindBar = true
        textView.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        textView.textColor = Self.textColor
        textView.backgroundColor = Self.backgroundColor
        textView.textContainerInset = NSSize(width: 6, height: 6)
        scroll.drawsBackground = true
        scroll.backgroundColor = Self.backgroundColor
        context.coordinator.textView = textView
        context.coordinator.scrollView = scroll
        context.coordinator.sync(with: console)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.sync(with: console)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    @MainActor
    final class Coordinator {
        weak var textView: NSTextView?
        weak var scrollView: NSScrollView?
        /// totalAppended value up to which the text storage is current.
        private var seenTotal = 0
        private var seenClearCount = 0

        func sync(with console: BuildConsoleModel) {
            guard let textView, let storage = textView.textStorage else { return }
            let missing = console.totalAppended - seenTotal
            let cleared = console.clearCount != seenClearCount
            seenTotal = console.totalAppended
            seenClearCount = console.clearCount
            guard cleared || missing > 0 else { return }

            let wasAtBottom = isNearBottom
            if cleared || missing > console.lines.count {
                // Cleared, or the ring buffer trimmed lines we never showed —
                // rebuild wholesale from what's retained.
                let text = console.lines.isEmpty ? "" : console.lines.joined(separator: "\n") + "\n"
                storage.setAttributedString(attributed(text))
            } else {
                let newLines = console.lines.suffix(missing)
                storage.append(attributed(newLines.joined(separator: "\n") + "\n"))
            }
            if wasAtBottom {
                textView.scrollToEndOfDocument(nil)
            }
        }

        private var isNearBottom: Bool {
            guard let scrollView, let textView else { return true }
            let visible = scrollView.contentView.bounds
            return visible.maxY >= textView.bounds.height - 40
        }

        private func attributed(_ text: String) -> NSAttributedString {
            NSAttributedString(string: text, attributes: [
                .font: NSFont.monospacedSystemFont(ofSize: 11, weight: .regular),
                .foregroundColor: ConsoleTextView.textColor,
            ])
        }
    }
}
