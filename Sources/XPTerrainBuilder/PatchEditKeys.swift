import SwiftUI
import AppKit
import Combine

/// Edit mode's keys on the map window (patch-editor spec §4): ⌫ / ⌦ delete
/// the selected nodes and shapes, Esc clears the selection. A local key monitor like
/// `ScrollZoomCatcher`'s, so no view needs keyboard focus; keys typed into
/// a text field (the elevation field, the search box) are left alone.
/// ⌘Z / ⇧⌘Z come from the Edit menu (the window's undo manager), ⌘S from
/// the File menu (`PatchSaveCommand`).
struct PatchKeyCatcher: NSViewRepresentable {
    let model: PatchEditModel

    final class Catcher: NSView {
        weak var model: PatchEditModel?
        private var monitor: Any?
        private var selectionWatch: AnyCancellable?

        override func hitTest(_ point: NSPoint) -> NSView? { nil }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if let monitor { NSEvent.removeMonitor(monitor) }
            monitor = nil
            guard window != nil else { return }
            watchSelection()
            monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
                guard let self, let window = self.window, event.window === window else { return event }
                // #1694: ⌘S saves the patch from anywhere in the map window,
                // even a text field (the File-menu item's disabled state can
                // go stale in SwiftUI commands).
                if PatchEditModel.isSaveShortcut(event.charactersIgnoringModifiers ?? "",
                                                 flags: event.modifierFlags) {
                    let saved = MainActor.assumeIsolated { () -> Bool in
                        guard let model = self.model, model.canSaveFromKey else { return false }
                        Task { await model.save() }
                        return true
                    }
                    return saved ? nil : event
                }
                guard !(window.firstResponder is NSText),
                      event.modifierFlags.isDisjoint(with: [.command, .control, .option]) else { return event }
                let handled = MainActor.assumeIsolated { self.model?.handleKey(event.keyCode) ?? false }
                return handled ? nil : event
            }
        }

        /// #1693: a selection takes focus off a text field (the search box)
        /// so ⌫ / ⌦ reach the selected nodes and shapes.
        func watchSelection() {
            selectionWatch = nil
            guard let model else { return }
            selectionWatch = model.$selection.combineLatest(model.$shapeSelection)
                .dropFirst()
                .receive(on: RunLoop.main)
                .sink { [weak self] _, _ in
                    MainActor.assumeIsolated {
                        guard let self, let window = self.window, let model = self.model,
                              model.selectionTakesFocus,
                              window.firstResponder is NSText else { return }
                        window.makeFirstResponder(nil)
                    }
                }
        }

        deinit {
            if let monitor { NSEvent.removeMonitor(monitor) }
        }
    }

    func makeNSView(context: Context) -> Catcher {
        let view = Catcher()
        view.model = model
        return view
    }

    func updateNSView(_ view: Catcher, context: Context) {
        if view.model !== model {
            view.model = model
            view.watchSelection()
        }
    }
}

extension PatchEditModel {
    static let deleteKey: UInt16 = 51
    static let forwardDeleteKey: UInt16 = 117
    static let escapeKey: UInt16 = 53

    /// ⌘S alone (no ⇧ / ⌥ / ⌃), #1694.
    nonisolated static func isSaveShortcut(_ chars: String, flags: NSEvent.ModifierFlags) -> Bool {
        chars.lowercased() == "s"
            && flags.intersection([.command, .shift, .option, .control]) == .command
    }

    /// The Save button's condition: a shown patch with unsaved edits.
    var canSaveFromKey: Bool { isShowing && unsavedEdits > 0 && !isSaving }

    /// Whether a selection should take keyboard focus from a text field
    /// (#1693): in Edit mode, with something selected.
    var selectionTakesFocus: Bool {
        Self.selectionTakesFocus(editing: mode == .edit, showing: isShowing, selected: hasSelection)
    }

    nonisolated static func selectionTakesFocus(editing: Bool, showing: Bool, selected: Bool) -> Bool {
        editing && showing && selected
    }

    /// Whether Edit mode consumed the key.
    func handleKey(_ keyCode: UInt16) -> Bool {
        guard mode == .edit, isShowing, hasSelection else { return false }
        switch keyCode {
        case Self.deleteKey, Self.forwardDeleteKey:
            deleteSelection()
            return true
        case Self.escapeKey:
            clearSelection()
            return true
        default:
            return false
        }
    }
}
