import SwiftUI
import AppKit

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

        override func hitTest(_ point: NSPoint) -> NSView? { nil }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if let monitor { NSEvent.removeMonitor(monitor) }
            monitor = nil
            guard window != nil else { return }
            monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
                guard let self, let window = self.window, event.window === window,
                      !(window.firstResponder is NSText),
                      event.modifierFlags.isDisjoint(with: [.command, .control, .option]) else { return event }
                let handled = MainActor.assumeIsolated { self.model?.handleKey(event.keyCode) ?? false }
                return handled ? nil : event
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
        view.model = model
    }
}

extension PatchEditModel {
    static let deleteKey: UInt16 = 51
    static let forwardDeleteKey: UInt16 = 117
    static let escapeKey: UInt16 = 53

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
