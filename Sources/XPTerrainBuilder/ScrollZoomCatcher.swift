import SwiftUI
import AppKit

/// Delivers scroll-wheel and trackpad-pinch events to the map without
/// interfering with clicks or drags. SwiftUI has no scroll-wheel gesture, so
/// this installs local event monitors and consumes events whose cursor is
/// over the catcher's frame; hitTest is nil so mouse events pass through to
/// the SwiftUI gestures beneath.
struct ScrollZoomCatcher: NSViewRepresentable {
    /// (location in SwiftUI coords, adjusted delta)
    let onScroll: (CGPoint, Double) -> Void
    let onMagnify: (CGPoint, Double) -> Void
    /// A right-click at a location → the menu to show there (#938), or nil
    /// to let the click through.
    var onRightClick: ((CGPoint) -> TileContextMenu?)? = nil

    final class Catcher: NSView {
        var onScroll: ((CGPoint, Double) -> Void)?
        var onMagnify: ((CGPoint, Double) -> Void)?
        var onRightClick: ((CGPoint) -> TileContextMenu?)?
        private var monitors: [Any] = []

        override func hitTest(_ point: NSPoint) -> NSView? { nil }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            removeMonitors()
            guard window != nil else { return }

            monitors.append(NSEvent.addLocalMonitorForEvents(matching: .scrollWheel) { [weak self] event in
                guard let self, let location = self.locationIfInside(event) else { return event }
                let delta = event.hasPreciseScrollingDeltas
                    ? Double(event.scrollingDeltaY)
                    : Double(event.scrollingDeltaY) * 10
                self.onScroll?(location, delta)
                return nil
            } as Any)

            monitors.append(NSEvent.addLocalMonitorForEvents(matching: .magnify) { [weak self] event in
                guard let self, let location = self.locationIfInside(event) else { return event }
                self.onMagnify?(location, Double(event.magnification))
                return nil
            } as Any)

            monitors.append(NSEvent.addLocalMonitorForEvents(matching: .rightMouseDown) { [weak self] event in
                guard let self, let location = self.locationIfInside(event),
                      let holder = self.onRightClick?(location) else { return event }
                // Synchronous: the menu's target stays alive while it is open.
                withExtendedLifetime(holder) {
                    NSMenu.popUpContextMenu(holder.menu, with: event, for: self)
                }
                return nil
            } as Any)
        }

        private func locationIfInside(_ event: NSEvent) -> CGPoint? {
            guard let window, event.window === window else { return nil }
            let local = convert(event.locationInWindow, from: nil)
            guard bounds.contains(local) else { return nil }
            // Flip to SwiftUI's top-left origin.
            return CGPoint(x: local.x, y: bounds.height - local.y)
        }

        func removeMonitors() {
            monitors.forEach { NSEvent.removeMonitor($0) }
            monitors = []
        }

        deinit { removeMonitors() }
    }

    func makeNSView(context: Context) -> Catcher {
        let view = Catcher()
        view.onScroll = onScroll
        view.onMagnify = onMagnify
        view.onRightClick = onRightClick
        return view
    }

    func updateNSView(_ view: Catcher, context: Context) {
        view.onScroll = onScroll
        view.onMagnify = onMagnify
        view.onRightClick = onRightClick
    }

    static func dismantleNSView(_ view: Catcher, coordinator: ()) {
        view.removeMonitors()
    }
}
