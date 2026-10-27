import SwiftUI
import AppKit
import SceneryKit

/// Bottom pane in Build mode: the engine's console output, streamed live.
/// Same slot the results pane occupies in Manage mode.
struct BuildConsoleView: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject private var consoleState: BuildConsoleModel

    init(console: BuildConsoleModel) {
        _consoleState = ObservedObject(wrappedValue: console)
    }

    var body: some View {
        // No bottom status bar: the run clock and remaining estimate live
        // in the Activity box (owner 2026-07-23 — duplicating them here
        // invited drift between the two displays, and the console rows
        // are worth more).
        VStack(spacing: 0) {
            header
            Divider()
            HStack(spacing: 0) {
                ConsoleTextView(console: buildModel.console)
                if consoleState.showHistory {
                    Divider()
                    BuildHistoryView()
                        .frame(width: 320)
                }
            }
        }
    }

    /// Title, the selection filter chip, the Saved logs menu, the Build
    /// History toggle and Clear (#1226). Mirrored by the Qt drawer's
    /// header (`O4_Qt_Build_History.ConsoleDrawer`).
    private var header: some View {
        HStack(spacing: 8) {
            Text("Build Console")
                .scaledFont(.headline)
            filterChip
            Spacer()
            savedLogsMenu
            Button {
                consoleState.showHistory.toggle()
            } label: {
                Image(systemName: "clock.arrow.circlepath")
            }
            .buttonStyle(.borderless)
            .help(consoleState.showHistory ? "Hide build history" : "Show build history")
            Button {
                buildModel.console.clear()
                buildModel.syncConsoleView()
            } label: {
                Image(systemName: "xmark.circle")
            }
            .buttonStyle(.borderless)
            .help("Clear the console (saved logs are kept)")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    /// "Showing +47-123, +47-122 ✕": the console follows the map
    /// selection; ✕ shows everything until the selection changes.
    @ViewBuilder
    private var filterChip: some View {
        let tiles = buildModel.consoleFilterTiles
        if let chosen = consoleState.chosenLog {
            chip("Saved log of \(chosen.tile)") {
                consoleState.chosenLog = nil
                buildModel.syncConsoleView()
            }
        } else if !tiles.isEmpty {
            let names = tiles.prefix(4).map(\.key).joined(separator: ", ")
                + (tiles.count > 4 ? " …" : "")
            chip("Showing \(names)") {
                consoleState.filterDismissed = true
                buildModel.syncConsoleView()
            }
        }
    }

    private func chip(_ text: String, clear: @escaping () -> Void) -> some View {
        HStack(spacing: 4) {
            Text(text)
                .scaledFont(.caption)
                .lineLimit(1)
            Button(action: clear) {
                Image(systemName: "xmark")
                    .scaledFont(.caption2)
            }
            .buttonStyle(.borderless)
            .help("Show every tile's lines")
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 2)
        .background(.quaternary, in: Capsule())
    }

    /// The active tile's kept builds (newest 3); picking one shows that
    /// build's saved log alone.
    private var savedLogsMenu: some View {
        let coord = buildModel.activeTile
        let records = coord.map { buildModel.savedLogs(for: $0) } ?? []
        return Menu("Saved logs") {
            if consoleState.chosenLog != nil {
                Button("Live console") {
                    consoleState.chosenLog = nil
                    buildModel.syncConsoleView()
                }
                Divider()
            }
            ForEach(records, id: \.log) { record in
                Button(Self.savedLogTitle(record)) {
                    guard let coord else { return }
                    consoleState.chosenLog = (coord.key, record.log)
                    buildModel.syncConsoleView()
                }
            }
        }
        .menuStyle(.borderlessButton)
        .fixedSize()
        .disabled(records.isEmpty)
        .help(records.isEmpty
              ? "The selected tile has no saved build log"
              : "Show one of the selected tile's last \(records.count) build logs")
    }

    static func savedLogTitle(_ record: TileBuildRecord) -> String {
        let when = Date(timeIntervalSince1970: record.end)
            .formatted(date: .abbreviated, time: .shortened)
        return "\(when) — \(record.outcomeText)"
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
        context.coordinator.setTextScale(context.environment.textScale)
        context.coordinator.sync(with: console)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.setTextScale(context.environment.textScale)
        context.coordinator.sync(with: console)
    }

    /// The console's point size at Actual Size; View ▸ text size scales it (#827).
    static let basePointSize = 11.0

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
        private var seenViewGeneration = 0
        private var fontSize = CGFloat(ConsoleTextView.basePointSize)

        private var font: NSFont { .monospacedSystemFont(ofSize: fontSize, weight: .regular) }

        /// Re-fonts the whole console when the text scale changes (#827).
        func setTextScale(_ scale: Double) {
            let size = CGFloat(TextScale.scaled(ConsoleTextView.basePointSize, scale))
            guard let textView, size != fontSize || textView.font?.pointSize != size else { return }
            fontSize = size
            textView.font = font
            if let storage = textView.textStorage, storage.length > 0 {
                storage.addAttribute(.font, value: font,
                                     range: NSRange(location: 0, length: storage.length))
            }
        }

        func sync(with console: BuildConsoleModel) {
            guard let textView, let storage = textView.textStorage else { return }
            let missing = console.totalAppended - seenTotal
            let cleared = console.clearCount != seenClearCount
                || console.viewGeneration != seenViewGeneration
            seenTotal = console.totalAppended
            seenClearCount = console.clearCount
            seenViewGeneration = console.viewGeneration
            guard cleared || missing > 0 else { return }

            let wasAtBottom = isNearBottom
            if cleared || missing > console.entries.count {
                // Cleared, re-filtered (#1226), or the ring buffer trimmed
                // lines we never showed — rebuild wholesale from what's
                // retained.
                let lines = console.visibleLines
                let text = lines.isEmpty ? "" : lines.joined(separator: "\n") + "\n"
                storage.setAttributedString(attributed(text))
            } else {
                let newLines = console.entries.suffix(missing).filter(console.shows).map(\.text)
                guard !newLines.isEmpty else { return }
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
                .font: font,
                .foregroundColor: ConsoleTextView.textColor,
            ])
        }
    }
}
