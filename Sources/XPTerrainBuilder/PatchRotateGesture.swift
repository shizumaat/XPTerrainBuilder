import SwiftUI
import AppKit
import SceneryKit

// Option-drag rotates a shape (#1746; Qt: Alt, `O4_Qt_Patch_Gestures`):
// with ⌥ held, the cursor over a shape's node is a rotate arrow, and a
// drag from there turns the shape (`PatchShapePick.rotationShapes`) about
// its centre (`PatchDocument.rotationCentre`). Like a move, the drag draws
// the turned shape from the pointer angle and commits ONE edit on mouse-up
// ("Rotate Shape", undoable); node elevations are kept.

extension NSCursor {
    /// A circular arrow (white under black, readable on any imagery);
    /// Qt draws the same in `O4_Qt_Rotate_Cursor`.
    static let patchRotate: NSCursor = {
        let size = NSSize(width: 24, height: 24)
        let image = NSImage(size: size, flipped: false) { _ in
            let c = NSPoint(x: 12, y: 12), r: CGFloat = 7
            let arc = NSBezierPath()
            arc.appendArc(withCenter: c, radius: r, startAngle: 120, endAngle: 60, clockwise: false)
            let end = NSPoint(x: c.x + r * cos(.pi / 3), y: c.y + r * sin(.pi / 3))
            let head = NSBezierPath()
            head.move(to: NSPoint(x: end.x + 6, y: end.y))
            head.line(to: end)
            head.line(to: NSPoint(x: end.x + 3, y: end.y - 5))
            for (colour, width) in [(NSColor.white, CGFloat(4)), (.black, 2)] {
                colour.setStroke()
                for path in [arc, head] {
                    path.lineWidth = width
                    path.lineCapStyle = .round
                    path.lineJoinStyle = .round
                    path.stroke()
                }
            }
            return true
        }
        return NSCursor(image: image, hotSpot: NSPoint(x: 12, y: 12))
    }()
}

/// Whether ⌥ is down, published so the cursor turns into the rotate arrow
/// (and back) without the pointer moving.
final class PatchOptionKey: ObservableObject {
    @Published private(set) var held = NSEvent.modifierFlags.contains(.option)
    private var monitor: Any?

    init() {
        monitor = NSEvent.addLocalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            let held = event.modifierFlags.contains(.option)
            if self?.held != held { self?.held = held }
            return event
        }
    }

    deinit {
        if let monitor { NSEvent.removeMonitor(monitor) }
    }
}

extension PatchDragState {
    /// The pointer angle since the press, in degrees counter-clockwise on
    /// the ground (screen y points down, so the screen angle flips sign).
    static func rotation(from start: CGPoint, to point: CGPoint, about pivot: CGPoint) -> Double {
        let a0 = atan2(start.y - pivot.y, start.x - pivot.x)
        let a1 = atan2(point.y - pivot.y, point.x - pivot.x)
        var d = -(a1 - a0) * 180 / .pi
        if d > 180 { d -= 360 } else if d < -180 { d += 360 }
        return d
    }
}

extension PatchEditModel {
    /// The Option-drag's ONE edit: turn the shapes by `degrees` about their
    /// centre.
    func rotateShapes(_ ways: Set<Int64>, degrees: Double) {
        guard !ways.isEmpty, abs(degrees) > 1.0e-9 else { return }
        lastShapeClick = nil
        perform(ways.count == 1 ? "Rotate Shape" : "Rotate Shapes") {
            try $0.rotateWays(ways.sorted(), degrees: degrees)
        }
    }
}
