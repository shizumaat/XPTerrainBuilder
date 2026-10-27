import AppKit
import SwiftUI

/// The fill behind an Activity or Completed row whose tile is selected
/// (#1537; which rows: `ActivityOrder.filledRows`). It raises contrast
/// against the group box: the system text background taken halfway on
/// away from the label colour — near-black in Dark Mode against the
/// dark-gray box, white in light mode against the light-gray one — so it
/// follows the appearance (Qt: `O4_Qt_Click_Row.fill_color`, from the
/// palette).
enum ActivityRowFill {
    static let system = NSColor(name: nil) { appearance in
        var out = NSColor.textBackgroundColor
        appearance.performAsCurrentDrawingAppearance {
            out = awayFromText(NSColor.textBackgroundColor)
        }
        return out
    }
    static var color: Color { Color(nsColor: system) }
    /// How far the fill reaches outside the row's content.
    static let margin: CGFloat = 3
    static let cornerRadius: CGFloat = 5

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
        background {
            if selected {
                RoundedRectangle(cornerRadius: ActivityRowFill.cornerRadius)
                    .fill(ActivityRowFill.color)
                    .padding(-ActivityRowFill.margin)
            }
        }
    }
}
