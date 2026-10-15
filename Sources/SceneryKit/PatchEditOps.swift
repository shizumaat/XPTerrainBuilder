import Foundation

// The patch editor's edit operations (Ortho4XP/docs/specs/patch-editor-20261015.md
// §3), the Swift twin of `Ortho4XP/src/o4_engine/patch_edit.py`. Both run
// `Ortho4XP/tests/fixtures/patch_edit_ops.json`, so the rules cannot drift:
//
// * a deleted node leaves every way;
// * after any op, consecutive duplicate refs collapse (cyclically on a
//   closed way); a closed way left with < 3 distinct nodes, or an open way
//   with < 2, is removed in the same step; nodes it leaves behind stay;
// * `mergeNodes` is the ONLY op that merges (the UI's snap decided);
//   moves, inserts, elevation edits and deletes never do.

/// Why an edit operation refused (the engine raises the same cases).
public enum PatchEditError: Error, Equatable, CustomStringConvertible {
    case unknownNode(Int64)
    case notAnEdge(Int64, Int64)
    case nodeExists(Int64)
    case mergeIntoItself(Int64)

    public var description: String {
        switch self {
        case .unknownNode(let id): return "node \(id) is not in the patch"
        case .notAnEdge(let a, let b): return "nodes \(a) and \(b) are not an edge of any way"
        case .nodeExists(let id): return "node \(id) already exists"
        case .mergeIntoItself(let id): return "cannot merge node \(id) into itself"
        }
    }
}

extension PatchDocument {
    /// Move the nodes by (dlat, dlon) degrees. Never merges.
    public mutating func move(_ ids: [Int64], dlat: Double, dlon: Double) throws {
        for id in try known(ids) {
            nodes[id]!.lat += dlat
            nodes[id]!.lon += dlon
        }
        reindex()
    }

    /// Put one node at (lat, lon). Never merges.
    public mutating func setPosition(_ id: Int64, lat: Double, lon: Double) throws {
        _ = try known([id])
        nodes[id]!.lat = lat
        nodes[id]!.lon = lon
        reindex()
    }

    /// Set the nodes' elevation (metres MSL; nil clears it).
    public mutating func setAlt(_ ids: [Int64], alt: Double?) throws {
        for id in try known(ids) { nodes[id]!.alt = alt }
    }

    /// Add `d` metres to the nodes' elevation; a node without one keeps none.
    public mutating func offsetAlt(_ ids: [Int64], by d: Double) throws {
        for id in try known(ids) where nodes[id]!.alt != nil { nodes[id]!.alt! += d }
    }

    /// Remove the nodes from the document and from every way (§3.2).
    public mutating func deleteNodes(_ ids: [Int64]) throws {
        let gone = Set(try known(ids))
        for id in gone { nodes[id] = nil }
        nodeOrder.removeAll { gone.contains($0) }
        ways = Self.rewrite(ways, remap: [:], dropped: gone)
        reindex()
    }

    /// Insert a node at the midpoint of edge a–b — alt the mean of the
    /// ends, nil if either has none — into EVERY way where a and b are
    /// consecutive in either direction (shared edges stay welded).
    /// Returns the new node's id (`nextNewNodeID` unless `id` is given).
    @discardableResult
    public mutating func insertOnEdge(_ a: Int64, _ b: Int64, id: Int64? = nil) throws -> Int64 {
        guard a != b else { throw PatchEditError.notAnEdge(a, b) }
        _ = try known([a, b])
        let na = nodes[a]!, nb = nodes[b]!
        let newID = id ?? nextNewNodeID
        guard nodes[newID] == nil else { throw PatchEditError.nodeExists(newID) }
        var hit = false
        for w in ways.indices {
            let refs = ways[w].refs
            var out: [Int64] = []
            out.reserveCapacity(refs.count + 1)
            for (i, r) in refs.enumerated() {
                out.append(r)
                if i + 1 < refs.count, Set([r, refs[i + 1]]) == Set([a, b]) {
                    out.append(newID)
                    hit = true
                }
            }
            if out.count != refs.count { ways[w].refs = out }
        }
        guard hit else { throw PatchEditError.notAnEdge(a, b) }
        let alt: Double? = if let x = na.alt, let y = nb.alt { (x + y) / 2 } else { nil }
        nodes[newID] = PatchNode(id: newID, lat: (na.lat + nb.lat) / 2, lon: (na.lon + nb.lon) / 2, alt: alt)
        nodeOrder.append(newID)
        reindex()
        return newID
    }

    /// Merge `source` INTO `target` (§3.3): the target keeps its position
    /// and elevation, every ref to the source becomes the target, the source
    /// leaves the document, and the topology rules apply. No distance check.
    public mutating func mergeNodes(source: Int64, target: Int64) throws {
        guard source != target else { throw PatchEditError.mergeIntoItself(source) }
        _ = try known([source, target])
        nodes[source] = nil
        nodeOrder.removeAll { $0 == source }
        ways = Self.rewrite(ways, remap: [source: target], dropped: [])
        reindex()
    }

    // MARK: - Topology (§3.2)

    /// The ids, de-duplicated in order; throws on an unknown one.
    private func known(_ ids: [Int64]) throws -> [Int64] {
        var out: [Int64] = []
        for id in ids {
            guard nodes[id] != nil else { throw PatchEditError.unknownNode(id) }
            if !out.contains(id) { out.append(id) }
        }
        return out
    }

    /// Remap and drop refs, then tidy every way that changed.
    static func rewrite(_ ways: [PatchWay], remap: [Int64: Int64], dropped: Set<Int64>) -> [PatchWay] {
        var out: [PatchWay] = []
        out.reserveCapacity(ways.count)
        for way in ways {
            var refs = way.refs.compactMap { dropped.contains($0) ? nil : (remap[$0] ?? $0) }
            if refs == way.refs { out.append(way); continue }
            let closed = way.refs.count >= 2 && way.refs.first == way.refs.last
            if closed, let first = refs.first, first != refs.last { refs.append(first) }
            guard !refs.isEmpty, let tidy = tidy(refs, closed: closed) else { continue }
            var kept = way
            kept.refs = tidy
            out.append(kept)
        }
        return out
    }

    /// Collapse consecutive duplicates; nil when the way falls below 3
    /// distinct nodes (closed) or 2 (open).
    static func tidy(_ refs: [Int64], closed: Bool) -> [Int64]? {
        var out: [Int64] = []
        for r in closed ? Array(refs.dropLast()) : refs where out.last != r { out.append(r) }
        if closed {
            while out.count > 1, out.last == out.first { out.removeLast() }
            guard Set(out).count >= 3 else { return nil }
            return out + [out[0]]
        }
        return Set(out).count >= 2 ? out : nil
    }
}
