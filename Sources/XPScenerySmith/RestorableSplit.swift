import SwiftUI
import AppKit

/// The genuine AppKit split view, wrapped — because NSSplitView's
/// autosaveName is the standard mechanism for persisting divider positions
/// across launches, which SwiftUI's H/VSplitView cannot do. Divider
/// positions restore before first display, so nothing moves after the
/// window opens.
struct RestorableSplit<First: View, Second: View>: NSViewControllerRepresentable {
    enum Orientation {
        /// Panes side by side (HSplitView equivalent).
        case horizontal
        /// Panes stacked (VSplitView equivalent).
        case vertical
    }

    let orientation: Orientation
    let autosaveName: String
    var firstMin: CGFloat
    var secondMin: CGFloat
    var secondMax: CGFloat? = nil
    @ViewBuilder let first: () -> First
    @ViewBuilder let second: () -> Second

    func makeNSViewController(context: Context) -> NSSplitViewController {
        let controller = NSSplitViewController()
        // NSSplitView "vertical" means the DIVIDER is vertical (side-by-side).
        controller.splitView.isVertical = orientation == .horizontal
        controller.splitView.dividerStyle = .thin

        let firstItem = NSSplitViewItem(viewController: NSHostingController(rootView: first()))
        firstItem.minimumThickness = firstMin
        // The first pane (map / map+inspector) absorbs window resizes; the
        // second (inspector / results) holds the size the user gave it.
        firstItem.holdingPriority = NSLayoutConstraint.Priority(249)
        let secondItem = NSSplitViewItem(viewController: NSHostingController(rootView: second()))
        secondItem.minimumThickness = secondMin
        if let secondMax { secondItem.maximumThickness = secondMax }
        secondItem.holdingPriority = NSLayoutConstraint.Priority(251)

        controller.addSplitViewItem(firstItem)
        controller.addSplitViewItem(secondItem)
        controller.splitView.autosaveName = autosaveName
        return controller
    }

    func updateNSViewController(_ controller: NSSplitViewController, context: Context) {
        (controller.splitViewItems.first?.viewController
            as? NSHostingController<First>)?.rootView = first()
        (controller.splitViewItems.last?.viewController
            as? NSHostingController<Second>)?.rootView = second()
    }
}
