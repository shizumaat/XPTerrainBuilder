import CoreGraphics

/// Framing one 1°×1° tile (issue #816: clicking a tile's Activity row
/// shows that tile on the map).
extension MapCamera {
    /// Margin on each side of a framed tile, as a fraction of the tile —
    /// the Qt app's `TILE_FRAME_MARGIN` (degrees on a 1° tile).
    static let tileFrameMargin = 0.15

    /// The camera that shows the whole tile `(lat, lon)` centred in a
    /// viewport of `size`, with `margin` of the tile's size on each side.
    static func framing(tileLat lat: Int, lon: Int, in size: CGSize,
                        margin: Double = tileFrameMargin) -> MapCamera {
        let south = mercatorY(lat: Double(lat))
        let north = mercatorY(lat: Double(lat + 1))
        let span = 1 + 2 * margin
        var cam = MapCamera()
        cam.centerLon = Double(lon) + 0.5
        cam.centerLat = latitude(mercatorY: (south + north) / 2)
        if size.width > 0, size.height > 0 {
            cam.scale = min(Double(size.width) / span,
                            Double(size.height) / ((north - south) * span))
        } else {
            cam.scale = 120
        }
        cam.clamp(in: size)
        return cam
    }
}
