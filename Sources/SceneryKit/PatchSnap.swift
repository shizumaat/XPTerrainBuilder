import Foundation

/// The drag snap's choice of target (spec §3.3, owner A10 as clarified
/// 2026-10-15): the POINTER within `radius` points ON SCREEN of a
/// non-dragged node snaps the grabbed node onto it. A pure function of
/// screen points, so it is tested without a window.
public enum PatchSnap {
    /// The owner's radius: 8 pt on screen, at any zoom — the click radius.
    public static let radius: Double = 8

    public struct Candidate: Sendable {
        public let id: Int64
        /// Where the node is drawn, in view points.
        public let x: Double
        public let y: Double
        public let lat: Double
        public let lon: Double

        public init(id: Int64, x: Double, y: Double, lat: Double, lon: Double) {
            self.id = id; self.x = x; self.y = y; self.lat = lat; self.lon = lon
        }
    }

    /// The candidate nearest the pointer within `radius` (inclusive, as a
    /// click); equal distances go to the lowest `survivorKey` (the fixture's
    /// `ui_snap_reference`), then the lowest id. Callers pass only
    /// non-dragged nodes.
    public static func target(pointerX: Double, pointerY: Double, candidates: [Candidate],
                              identityDp: Int, radius: Double = radius) -> Int64? {
        var best: (c: Candidate, d: Double)?
        for c in candidates {
            let d = hypot(c.x - pointerX, c.y - pointerY)
            guard d <= radius else { continue }
            if let b = best {
                if d > b.d { continue }
                if d == b.d {
                    let kc = survivorKey(lat: c.lat, lon: c.lon, dp: identityDp)
                    let kb = survivorKey(lat: b.c.lat, lon: b.c.lon, dp: identityDp)
                    if kc > kb || (kc == kb && c.id > b.c.id) { continue }
                }
            }
            best = (c, d)
        }
        return best?.c.id
    }

    /// The engine's `survivor_key`: (round(lat, dp), round(lon, dp)).
    public static func survivorKey(lat: Double, lon: Double, dp: Int) -> SurvivorKey {
        let k = pow(10.0, Double(dp))
        return SurvivorKey(lat: (lat * k).rounded() / k, lon: (lon * k).rounded() / k)
    }

    public struct SurvivorKey: Comparable, Sendable {
        public let lat: Double
        public let lon: Double

        public static func < (a: SurvivorKey, b: SurvivorKey) -> Bool {
            (a.lat, a.lon) < (b.lat, b.lon)
        }
    }
}
