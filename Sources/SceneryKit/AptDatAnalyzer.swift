import Foundation

/// apt.dat pavement lint (Laminar: "Don't overlap pavement in apt.dat
/// files"; describe shapes "with the fewest number of nodes possible"):
///
/// - **APT-01**: a single taxiway polygon (row 110) with an excessive node
///   count — X-Plane tessellates what WED authored; thousand-node outlines
///   are pure triangulation and fill cost.
/// - **APT-02**: an airport whose total pavement node count is excessive.
/// - **APT-03**: pavement polygons layered on top of each other — formally
///   illegal per the apt.dat spec, costs fill rate, and can make pavement
///   disappear at some rendering settings.
///
/// All three are author-level findings (fixing means redrawing in WED), so
/// they land in Developer Debug.
public struct AptDatAnalyzer {

    static let maxAptBytes = 32 * 1024 * 1024
    static let polygonNodeWarn = 300     // heuristic, PITFALLS §4
    static let airportNodeWarn = 10_000  // heuristic, PITFALLS §4
    /// A polygon counts as "layered" when at least this share of its
    /// vertices sits strictly inside another pavement polygon — edge-touch
    /// overlaps ("a small overlapping intersection is not so bad", Laminar)
    /// stay quiet.
    static let overlapVertexShare = 0.8
    static let maxFindingsPerCheck = 5
    /// Overlap testing is O(pairs × vertices × edges); airports beyond
    /// these bounds skip APT-03 rather than stall a pipeline worker.
    static let maxPolygonsForOverlap = 150
    static let overlapSampleVertices = 48
    static let overlapOpsBudget = 2_000_000

    struct Polygon {
        var airport: String
        var description: String
        /// Outer ring vertices (holes are counted in nodeCount but not used
        /// for overlap testing).
        var outerRing: [(lat: Double, lon: Double)] = []
        var nodeCount = 0
    }

    public static func scanPack(_ pack: SceneryPack) -> [Finding] {
        guard !pack.airports.isEmpty else { return [] }
        let candidates = [
            pack.url.appendingPathComponent("Earth nav data/apt.dat"),
            pack.url.appendingPathComponent("Earth Nav Data/apt.dat"),
        ]
        guard let aptURL = candidates.first(where: { FileManager.default.fileExists(atPath: $0.path) }),
              let size = (try? FileManager.default.attributesOfItem(atPath: aptURL.path))?[.size] as? Int,
              size <= maxAptBytes,
              let text = TextFile.contents(of: aptURL, maxBytes: maxAptBytes)
        else { return [] }

        let polygons = parsePavement(text: text)
        guard !polygons.isEmpty else { return [] }
        var findings: [Finding] = []

        // APT-01: node-heavy polygons.
        let heavy = polygons.filter { $0.nodeCount > polygonNodeWarn }
        for polygon in heavy.sorted(by: { $0.nodeCount > $1.nodeCount }).prefix(maxFindingsPerCheck) {
            findings.append(Finding(
                checkID: "APT-01",
                severity: .info,
                category: .developerDebug,
                title: "\(polygon.nodeCount)-node taxiway polygon at \(polygon.airport)\(polygon.description.isEmpty ? "" : " (\(polygon.description))")",
                detail: "One pavement polygon in '\(pack.name)''s apt.dat uses \(polygon.nodeCount) nodes (heuristic ceiling: \(polygonNodeWarn)). X-Plane tessellates every node at runtime; WED guidance is to describe shapes with the fewest nodes possible and let bezier subdivision do the smoothing.",
                path: aptURL.path,
                suggestion: "The author can simplify the outline in WED (fewer nodes, bezier curves instead of many short segments).",
                url: URL(string: "https://developer.x-plane.com/article/airport-data-apt-dat-12-00-file-format-specification/"),
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        // APT-02: airport totals.
        var nodesPerAirport: [String: Int] = [:]
        for polygon in polygons {
            nodesPerAirport[polygon.airport, default: 0] += polygon.nodeCount
        }
        for (airport, nodes) in nodesPerAirport.sorted(by: { $0.value > $1.value })
            .filter({ $0.value > airportNodeWarn }).prefix(maxFindingsPerCheck) {
            findings.append(Finding(
                checkID: "APT-02",
                severity: .info,
                category: .developerDebug,
                title: "\(nodes.formatted()) pavement nodes at \(airport)",
                detail: "'\(pack.name)''s apt.dat spends \(nodes.formatted()) nodes on pavement at \(airport) (heuristic ceiling: \(airportNodeWarn.formatted())). Every node is runtime tessellation work, and pavement is fill-rate-bound on top of that.",
                path: aptURL.path,
                suggestion: "The author can merge adjacent polygons and simplify outlines in WED.",
                url: URL(string: "https://developer.x-plane.com/article/calculating-rendering-load/"),
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        // APT-03: layered pavement.
        findings.append(contentsOf: overlapFindings(
            polygons: polygons, pack: pack, aptURL: aptURL))

        return findings
    }

    // MARK: - Parsing

    /// Pavement polygons (row 110 + node rows 111–116). Linear features
    /// (120) and boundaries (130) share the node row codes, so rows are only
    /// accumulated while a 110 header is the active feature.
    static func parsePavement(text: String) -> [Polygon] {
        var polygons: [Polygon] = []
        var current: Polygon? = nil
        var currentAirport = "?"
        var ringClosed = false

        func finish() {
            if let polygon = current, polygon.nodeCount >= 3 {
                polygons.append(polygon)
            }
            current = nil
        }

        for lineSub in TextFile.lines(text) {
            let line = lineSub.trimmingCharacters(in: .whitespaces)
            guard !line.isEmpty else { continue }
            let parts = line.split(whereSeparator: { $0 == " " || $0 == "\t" }).map(String.init)
            guard let code = parts.first else { continue }
            switch code {
            case "1", "16", "17":
                finish()
                currentAirport = parts.count > 4 ? parts[4] : "?"
            case "1302":
                // Metadata override: `1302 icao_code KSEA` is the identifier
                // every other part of the app reports airports under.
                if parts.count > 2, parts[1] == "icao_code" {
                    currentAirport = parts[2]
                }
            case "110":
                finish()
                ringClosed = false
                current = Polygon(
                    airport: currentAirport,
                    description: parts.count > 4 ? parts[4...].joined(separator: " ") : "")
            case "111", "112", "113", "114", "115", "116":
                guard current != nil, parts.count >= 3,
                      let lat = Double(parts[1]), let lon = Double(parts[2]) else { continue }
                current?.nodeCount += 1
                // Only the outer ring (before the first loop close) feeds
                // the overlap test; holes just count nodes.
                if !ringClosed {
                    current?.outerRing.append((lat, lon))
                }
                if code == "113" || code == "114" { ringClosed = true }
            default:
                // Any other row ends the open pavement feature.
                if current != nil { finish() }
            }
        }
        finish()
        return polygons
    }

    // MARK: - Overlap

    static func overlapFindings(polygons: [Polygon], pack: SceneryPack, aptURL: URL) -> [Finding] {
        // Group by airport; overlap across airports is meaningless.
        var byAirport: [String: [Polygon]] = [:]
        for polygon in polygons where polygon.outerRing.count >= 4 {
            byAirport[polygon.airport, default: []].append(polygon)
        }

        var findings: [Finding] = []
        for (airport, group) in byAirport.sorted(by: { $0.key < $1.key }) {
            guard group.count >= 2, group.count <= maxPolygonsForOverlap else { continue }
            let boxes = group.map { boundingBox($0.outerRing) }
            var layeredPairs: [(inner: Polygon, outer: Polygon, share: Double)] = []
            // Unordered pairs: a duplicate stack must report ONCE, not
            // (A on B) plus (B on A). Bounded: point-in-polygon work is
            // O(vertices × edges), so tested vertices are sampled and an
            // overall budget stops runaway airports.
            var budget = overlapOpsBudget
            outer: for i in group.indices {
                for j in group.indices where j > i {
                    guard boxesIntersect(boxes[i], boxes[j]) else { continue }
                    guard budget > 0 else { break outer }
                    // Exact duplicates (WED copy-paste in place) first: the
                    // ray-cast counts boundary points as outside, so an
                    // identical ring would otherwise evade the test.
                    if ringsCoincide(group[i].outerRing, group[j].outerRing) {
                        layeredPairs.append((group[i], group[j], 1.0))
                        continue
                    }
                    // The spatially smaller polygon is the candidate
                    // "sitting on" the bigger one; sample its vertices
                    // against the other. (Bounding-box area, not node
                    // count — a 4-node apron can dwarf a 300-node pad.)
                    func boxArea(_ b: (minLat: Double, maxLat: Double, minLon: Double, maxLon: Double)) -> Double {
                        (b.maxLat - b.minLat) * (b.maxLon - b.minLon)
                    }
                    let (inner, outer) = boxArea(boxes[i]) <= boxArea(boxes[j]) ? (i, j) : (j, i)
                    let ring = group[inner].outerRing
                    let stride = Swift.max(1, ring.count / overlapSampleVertices)
                    var tested = 0, inside = 0
                    for k in Swift.stride(from: 0, to: ring.count, by: stride) {
                        tested += 1
                        if contains(group[outer].outerRing, ring[k]) { inside += 1 }
                    }
                    budget -= tested * group[outer].outerRing.count
                    if tested > 0, Double(inside) / Double(tested) >= overlapVertexShare {
                        layeredPairs.append((group[inner], group[outer], Double(inside) / Double(tested)))
                    }
                }
            }
            guard !layeredPairs.isEmpty else { continue }
            let examples = layeredPairs.prefix(4).map { pair in
                let a = pair.inner.description.isEmpty ? "a \(pair.inner.nodeCount)-node polygon" : "'\(pair.inner.description)'"
                let b = pair.outer.description.isEmpty ? "a \(pair.outer.nodeCount)-node polygon" : "'\(pair.outer.description)'"
                return "\(a) sits \(Int(pair.share * 100))% on top of \(b)"
            }
            findings.append(Finding(
                checkID: "APT-03",
                severity: .warning,
                category: .developerDebug,
                title: "Layered pavement at \(airport): \(layeredPairs.count) stacked polygon\(layeredPairs.count == 1 ? "" : "s")",
                detail: "Pavement polygons in '\(pack.name)''s apt.dat draw on top of each other at \(airport): \(examples.joined(separator: "; ")). The apt.dat spec forbids taxiway overlaps; stacked pavement burns fill rate and can make pavement disappear at some rendering settings (Laminar: \"Dude, Where's My Taxiway?\").",
                path: aptURL.path,
                suggestion: "The author should cut the lower polygon around the upper one in WED instead of layering.",
                url: URL(string: "https://developer.x-plane.com/2014/10/dude-wheres-my-taxiway/"),
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
            if findings.count >= maxFindingsPerCheck { break }
        }
        return findings
    }

    // MARK: - Geometry

    static func boundingBox(_ ring: [(lat: Double, lon: Double)]) -> (minLat: Double, maxLat: Double, minLon: Double, maxLon: Double) {
        var box = (minLat: Double.infinity, maxLat: -Double.infinity,
                   minLon: Double.infinity, maxLon: -Double.infinity)
        for p in ring {
            box.minLat = min(box.minLat, p.lat); box.maxLat = max(box.maxLat, p.lat)
            box.minLon = min(box.minLon, p.lon); box.maxLon = max(box.maxLon, p.lon)
        }
        return box
    }

    static func boxesIntersect(
        _ a: (minLat: Double, maxLat: Double, minLon: Double, maxLon: Double),
        _ b: (minLat: Double, maxLat: Double, minLon: Double, maxLon: Double)
    ) -> Bool {
        a.minLat <= b.maxLat && b.minLat <= a.maxLat
            && a.minLon <= b.maxLon && b.minLon <= a.maxLon
    }

    /// Same ring authored twice (equal node counts, every vertex within
    /// ~1 cm) — the in-place duplicate the ray-cast can't see.
    static func ringsCoincide(_ a: [(lat: Double, lon: Double)], _ b: [(lat: Double, lon: Double)]) -> Bool {
        guard a.count == b.count, !a.isEmpty else { return false }
        let epsilon = 1e-7 // ≈1 cm in degrees
        for i in a.indices {
            if abs(a[i].lat - b[i].lat) > epsilon || abs(a[i].lon - b[i].lon) > epsilon {
                return false
            }
        }
        return true
    }

    /// Ray-cast point-in-polygon (strictly inside; boundary points count as
    /// outside, which is exactly the tolerance we want for edge-touching
    /// polygons).
    static func contains(_ ring: [(lat: Double, lon: Double)], _ point: (lat: Double, lon: Double)) -> Bool {
        var inside = false
        var j = ring.count - 1
        for i in ring.indices {
            let a = ring[i], b = ring[j]
            if (a.lat > point.lat) != (b.lat > point.lat) {
                let crossLon = (b.lon - a.lon) * (point.lat - a.lat) / (b.lat - a.lat) + a.lon
                if point.lon < crossLon { inside.toggle() }
            }
            j = i
        }
        return inside
    }
}
