import SwiftUI
import SceneryKit

/// The Favorite star (#2033; "pin" renamed Favorite, RULINGS 2026-11-10c
/// (1)): a Favorite is storage priority -- its sharp imagery is the last
/// made low-res when storage is tight. Any tile this app built, set a
/// build running or not (engine `imagery_pin`). Outlined, or filled on a
/// favorite; a click flips it. The Qt window's are
/// `O4_Qt_Imagery_OnDemand.FavoriteStar` (the tile pane) and
/// `O4_Qt_Map_Favorite` (the Build map), same geometry and words.
enum FavoriteStar {
    /// Below this square size on screen the map draws no star (Qt:
    /// `MIN_SQUARE_PX`).
    static let minSquarePx: CGFloat = 14
    static let color = Color(red: 1.0, green: 0.84, blue: 0.04) // #FFD60A

    /// The star's size and centre in tile square `rect` (screen points):
    /// top-right, 11-20 pt, a sixth of the square; nil when the square is
    /// too small to carry it.
    static func box(in rect: CGRect) -> (center: CGPoint, size: CGFloat)? {
        guard rect.width > minSquarePx else { return nil }
        let size = min(max(rect.width * 0.16, 11), 20)
        return (CGPoint(x: rect.maxX - size * 0.7, y: rect.minY + size * 0.7), size)
    }

    /// Does `point` fall on the star of tile square `rect`?
    static func hit(_ point: CGPoint, in rect: CGRect) -> Bool {
        guard let box = box(in: rect) else { return false }
        return abs(point.x - box.center.x) <= box.size * 0.7
            && abs(point.y - box.center.y) <= box.size * 0.7
    }

    /// The star on the map: filled yellow on a favorite, a yellow outline
    /// over a dark halo on the others.
    static func draw(in context: GraphicsContext, rect: CGRect, pinned: Bool) {
        guard let box = box(in: rect) else { return }
        if !pinned {
            context.draw(Text(Image(systemName: "star.fill"))
                            .font(.system(size: box.size))
                            .foregroundStyle(.black.opacity(0.35)),
                         at: box.center)
        }
        context.draw(Text(Image(systemName: pinned ? "star.fill" : "star"))
                        .font(.system(size: box.size))
                        .foregroundStyle(color),
                     at: box.center)
    }
}

/// The star beside the tile pane's title: outlined, or filled on a
/// favorite; a click asks for the other state.
struct FavoriteStarButton: View {
    let pinned: Bool
    /// Favorite or not; a sentence for the user (the reply or the error).
    let setPinned: (Bool) async -> String

    @State private var working = false

    var body: some View {
        Button {
            working = true
            Task {
                _ = await setPinned(!pinned)
                working = false
            }
        } label: {
            Image(systemName: pinned ? "star.fill" : "star")
                .foregroundStyle(pinned ? FavoriteStar.color : .secondary)
        }
        .buttonStyle(.borderless)
        .disabled(working)
        .help(O4OnDemandText.starHelp(pinned))
        .accessibilityLabel(O4OnDemandText.favoriteTitle)
    }
}
