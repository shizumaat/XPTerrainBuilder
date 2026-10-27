import AppKit
import SwiftUI

/// The fill behind an Activity or Completed row whose tile is selected
/// (#1537; which rows: `ActivityOrder.filledRows`). It raises contrast
/// against the group box, subtly (owner on 1.0.438): the pane colour
/// (`underPageBackgroundColor`, the system gray nearest the group box's
/// tint — the window background is plain white in light mode) moved a quarter of the way to the system text background
/// taken halfway on away from the label colour — darker in Dark Mode,
/// lighter in light mode — so it follows the appearance. It spans the
/// box edge to edge with square corners (Qt: `O4_Qt_Click_Row.fill_color`,
/// from the palette).
enum ActivityRowFill {
    static let system = NSColor(name: nil) { appearance in
        var out = NSColor.textBackgroundColor
        appearance.performAsCurrentDrawingAppearance {
            out = subtle(pane: NSColor.underPageBackgroundColor,
                         text: NSColor.textBackgroundColor)
        }
        return out
    }
    static var color: Color { Color(nsColor: system) }
    /// How far the fill reaches above and below the row's content.
    static let margin: CGFloat = 3
    /// Square corners: the fill is a band across the box.
    static let cornerRadius: CGFloat = 0
    /// How far the fill reaches sideways: out to the box's edges.
    static var sideReach: CGFloat { PaneBoxMetrics.edgeInset }
    /// The share of the old (#1537) contrast step kept.
    static let step: CGFloat = 0.25

    /// `pane` moved `step` of the way to `awayFromText(text)`.
    static func subtle(pane: NSColor, text: NSColor) -> NSColor {
        let a = pane.usingColorSpace(.sRGB) ?? pane
        let b = awayFromText(text)
        func mix(_ x: CGFloat, _ y: CGFloat) -> CGFloat { x + (y - x) * step }
        return NSColor(srgbRed: mix(a.redComponent, b.redComponent),
                       green: mix(a.greenComponent, b.greenComponent),
                       blue: mix(a.blueComponent, b.blueComponent),
                       alpha: a.alphaComponent)
    }

    /// `background` halfway to black when it is dark, to white when light.
    static func awayFromText(_ background: NSColor) -> NSColor {
        let rgb = background.usingColorSpace(.sRGB) ?? background
        let light = rgb.redComponent + rgb.greenComponent + rgb.blueComponent > 1.5
        return rgb.halfway(toward: light ? 1 : 0)
    }
}

extension NSColor {
    /// This colour taken halfway, in sRGB, to the gray `level` (1 white,
    /// 0 black); alpha kept.
    func halfway(toward level: CGFloat) -> NSColor {
        let rgb = usingColorSpace(.sRGB) ?? self
        return NSColor(srgbRed: (rgb.redComponent + level) / 2,
                       green: (rgb.greenComponent + level) / 2,
                       blue: (rgb.blueComponent + level) / 2,
                       alpha: rgb.alphaComponent)
    }
}

extension View {
    /// Fill behind the row when `selected` (`ActivityRowFill`).
    func activityRowFill(_ selected: Bool) -> some View {
        frame(maxWidth: .infinity, alignment: .leading).background {
            if selected {
                Rectangle()
                    .fill(ActivityRowFill.color)
                    .padding(.vertical, -ActivityRowFill.margin)
                    .padding(.horizontal, -ActivityRowFill.sideReach)
            }
        }
    }
}
