import AppKit
import SwiftUI

/// Value description of one outline row. The tree is rebuilt every SwiftUI
/// update; the coordinator maps it onto long-lived node objects so the
/// outline's expansion and selection survive the ~0.4 s streaming reloads.
struct OutlineNodeSpec {
    let id: String
    /// Row content, hosted in the cell. Must carry its own environment
    /// objects — hosting views do not inherit the SwiftUI environment.
    let view: AnyView
    /// Set for selectable finding rows (drives Fix Selected); headers,
    /// tables and detail rows are nil and unselectable.
    var findingID: UUID? = nil
    /// Expand this node the FIRST time it appears (errors on screen after
    /// a fresh run); never overrides a collapse the user made later.
    var defaultExpanded = false
    var typeSelect = ""
    var children: [OutlineNodeSpec] = []
}

/// The results hierarchy as a real NSOutlineView — native gutter chevrons
/// and per-level indentation, arrow-key expand/collapse, ⌥-click
/// expand-all, type-select — with SwiftUI cells hosted per row
/// (`usesAutomaticRowHeights` sizes them). No subclassing: structure and
/// behavior are the outline's own, so future macOS appearance changes
/// apply themselves; we only supply data and row content.
struct ResultsOutlineView: NSViewRepresentable {
    let roots: [OutlineNodeSpec]
    let selection: Set<UUID>
    let onSelectionChange: (Set<UUID>) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelectionChange: onSelectionChange)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let outline = NSOutlineView()
        let column = NSTableColumn(identifier: .init("main"))
        column.resizingMask = .autoresizingMask
        outline.addTableColumn(column)
        outline.outlineTableColumn = column
        outline.headerView = nil
        outline.usesAutomaticRowHeights = true
        outline.allowsMultipleSelection = true
        outline.autoresizesOutlineColumn = false
        outline.columnAutoresizingStyle = .firstColumnOnlyAutoresizingStyle
        outline.style = .inset
        outline.rowSizeStyle = .default
        outline.dataSource = context.coordinator
        outline.delegate = context.coordinator
        outline.target = context.coordinator
        // Double-clicking a group row toggles it, like Finder's list view.
        outline.doubleAction = #selector(Coordinator.rowDoubleClicked(_:))
        context.coordinator.outline = outline

        let scroll = NSScrollView()
        scroll.documentView = outline
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.onSelectionChange = onSelectionChange
        context.coordinator.apply(specs: roots, selection: selection)
    }

    /// Outline item: reference type with stable identity per spec id. The
    /// outline tracks expansion by item identity, so reusing instances
    /// across reloads is what keeps open groups open.
    final class Node: NSObject {
        let nodeID: String
        var spec: OutlineNodeSpec
        var children: [Node] = []

        init(spec: OutlineNodeSpec) {
            self.nodeID = spec.id
            self.spec = spec
        }
    }

    final class Coordinator: NSObject, NSOutlineViewDataSource, NSOutlineViewDelegate {
        weak var outline: NSOutlineView?
        var onSelectionChange: (Set<UUID>) -> Void
        private var roots: [Node] = []
        private var cache: [String: Node] = [:]
        /// Ids that have appeared before — defaultExpanded fires once per
        /// node, so a user's later collapse is never fought.
        private var seen: Set<String> = []
        private var isSyncing = false

        init(onSelectionChange: @escaping (Set<UUID>) -> Void) {
            self.onSelectionChange = onSelectionChange
        }

        func apply(specs: [OutlineNodeSpec], selection: Set<UUID>) {
            guard let outline else { return }
            var live = Set<String>()
            roots = specs.map { materialize($0, live: &live) }
            cache = cache.filter { live.contains($0.key) }

            isSyncing = true
            outline.reloadData()
            var firstTimers: [Node] = []
            collectFirstAppearance(roots, into: &firstTimers)
            // Preorder: parents expand before their children.
            for node in firstTimers { outline.expandItem(node) }
            restoreSelection(selection, in: outline)
            isSyncing = false
        }

        private func materialize(_ spec: OutlineNodeSpec, live: inout Set<String>) -> Node {
            live.insert(spec.id)
            let node = cache[spec.id] ?? Node(spec: spec)
            node.spec = spec
            node.children = spec.children.map { materialize($0, live: &live) }
            cache[spec.id] = node
            return node
        }

        private func collectFirstAppearance(_ nodes: [Node], into result: inout [Node]) {
            for node in nodes {
                if !seen.contains(node.nodeID) {
                    seen.insert(node.nodeID)
                    if node.spec.defaultExpanded { result.append(node) }
                }
                collectFirstAppearance(node.children, into: &result)
            }
        }

        private func restoreSelection(_ selection: Set<UUID>, in outline: NSOutlineView) {
            var indexes = IndexSet()
            for node in cache.values {
                guard let findingID = node.spec.findingID,
                      selection.contains(findingID) else { continue }
                let row = outline.row(forItem: node)
                if row >= 0 { indexes.insert(row) }
            }
            if outline.selectedRowIndexes != indexes {
                outline.selectRowIndexes(indexes, byExtendingSelection: false)
            }
        }

        // MARK: Data source

        func outlineView(_ outlineView: NSOutlineView, numberOfChildrenOfItem item: Any?) -> Int {
            (item as? Node)?.children.count ?? roots.count
        }

        func outlineView(_ outlineView: NSOutlineView, child index: Int, ofItem item: Any?) -> Any {
            ((item as? Node)?.children ?? roots)[index]
        }

        func outlineView(_ outlineView: NSOutlineView, isItemExpandable item: Any) -> Bool {
            guard let node = item as? Node else { return false }
            return !node.children.isEmpty
        }

        // MARK: Delegate

        func outlineView(_ outlineView: NSOutlineView, viewFor tableColumn: NSTableColumn?,
                         item: Any) -> NSView? {
            guard let node = item as? Node else { return nil }
            let identifier = NSUserInterfaceItemIdentifier("HostingCell")
            let cell = outlineView.makeView(withIdentifier: identifier, owner: nil)
                as? HostingCellView ?? HostingCellView(identifier: identifier)
            cell.setContent(node.spec.view)
            return cell
        }

        func outlineView(_ outlineView: NSOutlineView, shouldSelectItem item: Any) -> Bool {
            (item as? Node)?.spec.findingID != nil
        }

        func outlineViewSelectionDidChange(_ notification: Notification) {
            guard !isSyncing, let outline else { return }
            let ids = Set(outline.selectedRowIndexes.compactMap { row in
                (outline.item(atRow: row) as? Node)?.spec.findingID
            })
            onSelectionChange(ids)
        }

        func outlineView(_ outlineView: NSOutlineView, typeSelectStringFor tableColumn: NSTableColumn?,
                         item: Any) -> String? {
            let text = (item as? Node)?.spec.typeSelect ?? ""
            return text.isEmpty ? nil : text
        }

        @objc func rowDoubleClicked(_ sender: Any?) {
            guard let outline else { return }
            let row = outline.clickedRow
            guard row >= 0, let node = outline.item(atRow: row) as? Node,
                  !node.children.isEmpty, node.spec.findingID == nil else { return }
            if outline.isItemExpanded(node) {
                outline.animator().collapseItem(node)
            } else {
                outline.animator().expandItem(node)
            }
        }
    }

    /// Cell = one edge-pinned NSHostingView; automatic row heights read the
    /// hosted content's fitting size.
    final class HostingCellView: NSTableCellView {
        private var hosting: NSHostingView<AnyView>?

        convenience init(identifier: NSUserInterfaceItemIdentifier) {
            self.init(frame: .zero)
            self.identifier = identifier
        }

        func setContent(_ view: AnyView) {
            if let hosting {
                hosting.rootView = view
            } else {
                let host = NSHostingView(rootView: view)
                host.translatesAutoresizingMaskIntoConstraints = false
                addSubview(host)
                NSLayoutConstraint.activate([
                    host.leadingAnchor.constraint(equalTo: leadingAnchor),
                    host.trailingAnchor.constraint(equalTo: trailingAnchor),
                    host.topAnchor.constraint(equalTo: topAnchor),
                    host.bottomAnchor.constraint(equalTo: bottomAnchor),
                ])
                hosting = host
            }
        }
    }
}
