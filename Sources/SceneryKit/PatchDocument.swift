import Foundation

// The patch an airport's tile build uses, as the patch editor holds it
// (Ortho4XP/docs/specs/patch-editor-20261015.md §2–§4). Loaded from a
// `patch_load` reply; saved back through `patch_save` in the same order.
// The §3 edit operations are `mutating` members in `PatchEditOps.swift`,
// twin-tested against `Ortho4XP/tests/fixtures/patch_edit_ops.json`;
// after each op they call `reindex()` so `waysUsing` and `bbox` stay true.

public struct PatchNode: Equatable, Sendable {
    /// The file's (negative) id.
    public let id: Int64
    public var lat: Double
    public var lon: Double
    /// Metres MSL; nil for a hand-made patch whose node has no `alt_abs`
    /// (the build takes that point's elevation from the mesh).
    public var alt: Double?

    public init(id: Int64, lat: Double, lon: Double, alt: Double?) {
        self.id = id; self.lat = lat; self.lon = lon; self.alt = alt
    }
}

public struct PatchWay: Equatable, Sendable {
    public let id: Int64
    public var refs: [Int64]
    /// Written back unchanged by `patch_save`.
    public let tags: [String: String]
    public let style: PatchStyleClass

    public init(id: Int64, refs: [Int64], tags: [String: String]) {
        self.id = id; self.refs = refs; self.tags = tags
        self.style = PatchStyleClass(tags: tags)
    }

    /// First ref == last ref: a shape (filled), else a line.
    public var isClosed: Bool { refs.count > 2 && refs.first == refs.last }

    /// The role tag the inspector names ("used by"), else the aeroway.
    public var roleName: String? { tags["role"] ?? tags["aeroway"] ?? tags["highway"] }
}

/// How a way is drawn on the map — the legend's classes.
public enum PatchStyleClass: String, CaseIterable, Sendable {
    case runway, taxiway, apron, building, road
    /// Graded strips, clearances, adjacent ground, walls and the engine's
    /// helper shapes: drawn as thin outlines.
    case ground

    /// `role` wins over `aeroway` (the engine tags a graded strip
    /// `aeroway=apron` and a building `aeroway=apron` too); taxiway family
    /// roles (`primary_parallel`, `stub`, `junction`, …) fall through to
    /// their `aeroway=taxiway`.
    public init(tags: [String: String]) {
        if let role = tags["role"], let mapped = Self.roleClasses[role] { self = mapped; return }
        if let aeroway = tags["aeroway"], let mapped = Self.aerowayClasses[aeroway] {
            self = mapped; return
        }
        if tags["highway"] != nil { self = .road; return }
        if tags["building"] != nil { self = .building; return }
        self = .ground
    }

    static let roleClasses: [String: PatchStyleClass] = [
        "runway": .runway,
        "taxiway": .taxiway,
        "apron": .apron, "groundside_pavement": .apron,
        "building": .building,
        "service_road": .road, "service_junction": .road, "road": .road,
        "graded_strip": .ground, "runway_clearance": .ground, "ols_cut": .ground,
        "retaining_wall": .ground, "adjacent_ground": .ground,
    ]

    static let aerowayClasses: [String: PatchStyleClass] = [
        "runway": .runway, "taxiway": .taxiway, "apron": .apron,
        "building": .building, "aerodrome": .ground,
    ]
}

/// The linear local plane the engine's emit reasons in
/// (`emit/osm_adapter._local_metres`: 111,320 m per degree of latitude,
/// longitude scaled by cos(origin latitude)).
public struct PatchLocalFrame: Equatable, Sendable {
    public static let metresPerDegreeLat = 111_320.0

    public let originLat: Double
    public let originLon: Double
    public let metresPerDegreeLon: Double

    public init(originLat: Double, originLon: Double) {
        self.originLat = originLat
        self.originLon = originLon
        metresPerDegreeLon = Self.metresPerDegreeLat * max(cos(originLat * .pi / 180), 1.0e-6)
    }

    /// (east, north) metres from the origin.
    public func metres(lat: Double, lon: Double) -> (x: Double, y: Double) {
        ((lon - originLon) * metresPerDegreeLon, (lat - originLat) * Self.metresPerDegreeLat)
    }

    public func latLon(x: Double, y: Double) -> (lat: Double, lon: Double) {
        (originLat + y / Self.metresPerDegreeLat, originLon + x / metresPerDegreeLon)
    }
}

public struct PatchDocument: Equatable, Sendable {
    // What the file is (from `patch_load`).
    public let tile: String
    public let icao: String
    /// `source`, `path` and `header` change only through `markSaved(path:)`.
    public private(set) var source: O4PatchSource
    public private(set) var path: String
    public let stale: Bool
    public let staleInputs: [String]
    /// The law's own snap distance (§3.3) — served, never hard-coded.
    public let minDistinctSpacingM: Double
    public let identityDp: Int
    public private(set) var header: [String: String]

    // The geometry. `nodeOrder` is the file's order, which `patch_save`
    // keeps; L3's ops edit `nodes`/`ways` and then call `reindex()`.
    public var nodes: [Int64: PatchNode]
    public var nodeOrder: [Int64]
    public var ways: [PatchWay]

    // Derived by `reindex()`.
    public private(set) var bbox: O4LatLonBox?
    public private(set) var wayIndicesByNode: [Int64: [Int]] = [:]
    /// The §3.3 metric plane, at the loaded bbox's centre (fixed for the
    /// document's life so an edit never moves the frame under it).
    public let frame: PatchLocalFrame

    public init(tile: String, load: O4PatchLoad) {
        self.tile = tile
        icao = load.icao
        source = load.source
        path = load.path
        stale = load.stale
        staleInputs = load.staleInputs
        minDistinctSpacingM = load.minDistinctSpacingM
        identityDp = load.identityDp
        header = load.header
        var nodes: [Int64: PatchNode] = [:]
        nodes.reserveCapacity(load.nodes.count)
        for row in load.nodes {
            nodes[row.id] = PatchNode(id: row.id, lat: row.lat, lon: row.lon, alt: row.alt)
        }
        self.nodes = nodes
        nodeOrder = load.nodes.map(\.id)
        ways = load.ways.map { PatchWay(id: $0.id, refs: $0.refs, tags: $0.tags) }
        let box = Self.bounds(of: nodes.values)
        frame = PatchLocalFrame(originLat: box.map { ($0.minLat + $0.maxLat) / 2 } ?? 0,
                                originLon: box.map { ($0.minLon + $0.maxLon) / 2 } ?? 0)
        reindex()
    }

    /// Recompute `bbox` and the node → ways index after an edit.
    public mutating func reindex() {
        bbox = Self.bounds(of: nodes.values)
        var index: [Int64: [Int]] = [:]
        for (w, way) in ways.enumerated() {
            for ref in Set(way.refs) { index[ref, default: []].append(w) }
        }
        wayIndicesByNode = index
    }

    public func waysUsing(_ node: Int64) -> [PatchWay] {
        (wayIndicesByNode[node] ?? []).map { ways[$0] }
    }

    /// An editor-saved file (`o4_user_edited="1"`, §1.2), as opposed to a
    /// hand-made manual patch or the auto patch.
    public var isUserEdited: Bool { header["o4_user_edited"] == "1" }

    /// The editor's own file name for this airport (§1.2, A6).
    public static func editedFileName(icao: String) -> String { "\(icao)_edited.patch.osm" }

    /// A manual patch the editor did not name (a JOSM file): it saves back
    /// to itself and has no "Revert to auto" (`patch_revert` refuses it).
    /// Read from the file NAME — `patch_save` stamps `o4_user_edited` into
    /// such a file too.
    public var isHandMade: Bool {
        source == .manual && (path as NSString).lastPathComponent != Self.editedFileName(icao: icao)
    }

    /// After `patch_save` wrote the document to `path`: it is now that
    /// manual patch, carrying the editor's header mark.
    public mutating func markSaved(path: String) {
        self.path = path
        source = .manual
        header["o4_user_edited"] = "1"
    }

    /// Nodes the build takes from the mesh (no `alt_abs`).
    public var nodesWithoutElevation: Int { nodes.values.reduce(0) { $0 + ($1.alt == nil ? 1 : 0) } }

    /// Where a new node's id comes from (§2: below the document's minimum).
    public var nextNewNodeID: Int64 { min(nodeOrder.min() ?? 0, 0) - 1 }

    /// The `patch_save` payload: nodes in file order, ways as held.
    public var saveRows: (nodes: [O4PatchNodeRow], ways: [O4PatchWayRow]) {
        (nodeOrder.compactMap { id in nodes[id].map { O4PatchNodeRow(id: $0.id, lat: $0.lat, lon: $0.lon, alt: $0.alt) } },
         ways.map { O4PatchWayRow(id: $0.id, refs: $0.refs, tags: $0.tags) })
    }

    /// A way's bounding box in degrees (for viewport culling).
    public func bounds(ofWay way: PatchWay) -> O4LatLonBox? {
        Self.bounds(of: way.refs.lazy.compactMap { nodes[$0] })
    }

    static func bounds<S: Sequence>(of nodes: S) -> O4LatLonBox? where S.Element == PatchNode {
        var box: O4LatLonBox?
        for n in nodes {
            if var b = box {
                b.minLat = min(b.minLat, n.lat); b.maxLat = max(b.maxLat, n.lat)
                b.minLon = min(b.minLon, n.lon); b.maxLon = max(b.maxLon, n.lon)
                box = b
            } else {
                box = O4LatLonBox(minLat: n.lat, minLon: n.lon, maxLat: n.lat, maxLon: n.lon)
            }
        }
        return box
    }
}
