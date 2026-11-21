import CoreGraphics

/// A map pan's anchor: the camera when THIS drag began (#2214). SwiftUI
/// never calls `onEnded` for a drag it cancels (a layer appearing over the
/// map mid-drag, the patch layer leaving the screen while it pans), so an
/// anchor kept until `onEnded` outlived its gesture: the next drag — a
/// click that moved — put the map back on the old view, the airport
/// looked at before. The anchor is keyed by its gesture's start point; a
/// drag that starts anywhere else anchors afresh.
struct MapPanAnchor: Equatable {
    let start: CGPoint
    let camera: MapCamera

    /// `held` while it is this drag's own, else the camera now.
    static func current(_ held: MapPanAnchor?, start: CGPoint, camera: MapCamera) -> MapPanAnchor {
        if let held, held.start == start { return held }
        return MapPanAnchor(start: start, camera: camera)
    }
}
