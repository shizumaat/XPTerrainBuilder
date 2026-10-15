import AppKit
import Combine
import CoreGraphics
import SceneryKit

/// The 3D preview's imagery drape (patch-editor spec §5, round 6c): the
/// map's live-imagery tiles, asked of the app's `ImageryModel` — its memory
/// cache, then its disk cache, then its own download, never a second path —
/// painted into one texture over the preview extent (`PatchDrapePlan`,
/// ≤ 4096 px a side). Tiles are painted as they land; the canvas starts in
/// the terrain colour, so a missing tile reads as terrain.
@MainActor
final class TerrainPreviewDrape {
    private(set) var plan: PatchDrapePlan?
    private var context: CGContext?
    private var painted: Set<Int> = []
    private var code: String?
    private var subscription: AnyCancellable?
    private weak var imagery: ImageryModel?
    /// The texture so far (nil when there is no source).
    var onImage: ((CGImage?) -> Void)?

    /// Start (or restart) the drape for `box`.
    func start(box: O4LatLonBox, imagery: ImageryModel) {
        stop()
        self.imagery = imagery
        guard imagery.hasActiveSource,
              let plan = PatchDrapePlan(box: box, maxZoom: imagery.activeMaxZL) else {
            onImage?(nil)
            return
        }
        self.plan = plan
        code = imagery.activeLabel
        guard let ctx = CGContext(data: nil, width: plan.width, height: plan.height, bitsPerComponent: 8,
                                  bytesPerRow: 0, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            onImage?(nil)
            return
        }
        ctx.setFillColor(TerrainPreviewScene.terrainColor.cgColor)
        ctx.fill(CGRect(x: 0, y: 0, width: plan.width, height: plan.height))
        // CGContext's origin is bottom-left; the plan's rects are top-left
        ctx.translateBy(x: 0, y: CGFloat(plan.height))
        ctx.scaleBy(x: 1, y: -1)
        context = ctx
        subscription = imagery.$generation.sink { [weak self] _ in
            DispatchQueue.main.async { self?.paint() }
        }
        paint()
    }

    func stop() {
        subscription = nil
        context = nil
        plan = nil
        painted = []
    }

    /// The source changed on the map: restart if it is a different one.
    func sourceMayHaveChanged() {
        guard let imagery, let plan, imagery.activeLabel != code else { return }
        start(box: plan.box, imagery: imagery)
    }

    private func paint() {
        guard let plan, let context, let imagery else { return }
        var drew = false
        for (i, t) in plan.tiles.enumerated() where !painted.contains(i) {
            // ImageryModel schedules what it does not hold (disk, then its download)
            guard let hit = imagery.image(z: plan.zoom, x: t.x, y: t.y) else { continue }
            let r = plan.rect(x: t.x, y: t.y)
            context.saveGState()
            // draw the tile upright inside the flipped (top-left) context
            context.translateBy(x: r.minX, y: r.maxY)
            context.scaleBy(x: 1, y: -1)
            context.draw(hit.image, in: CGRect(x: 0, y: 0, width: r.width, height: r.height))
            context.restoreGState()
            painted.insert(i)
            drew = true
        }
        let done = painted.count == plan.tiles.count
        if done { subscription = nil }
        if drew { publish(now: done) }
    }

    /// A HECA-sized texture is ~180 MB: hand the scene a copy at most every
    /// half second while tiles stream in, and once more at the end.
    private var publishScheduled = false

    private func publish(now: Bool) {
        if now {
            onImage?(context?.makeImage())
            return
        }
        guard !publishScheduled else { return }
        publishScheduled = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self else { return }
            self.publishScheduled = false
            self.onImage?(self.context?.makeImage())
        }
    }
}
