import Foundation

/// "Set elevation…" on the selected patch shapes (issue #1357; Qt's
/// `O4_Qt_Patch_Elevation`). What one edit touches: every node of the
/// selected shapes, outer rings and their holes (the `gap_interior_ring`
/// rings `PatchShapeAssembly` pairs with them), split into the nodes only
/// they use and the nodes they share with other shapes; the neighbouring
/// shapes those shared nodes belong to; and the mean `alt_abs` that
/// prefills the field.
public struct PatchShapeElevation: Equatable, Sendable {
    /// The display units of the field.
    public enum Unit: String, CaseIterable, Sendable {
        case metres = "m", feet = "ft"
    }

    /// International foot (`PatchNodeInspector.feetPerMetre`).
    public static let feetPerMetre = 1 / 0.3048

    /// The selected way ids plus the holes paired with them.
    public let ways: Set<Int64>
    /// Nodes no other shape uses.
    public let own: Set<Int64>
    /// Nodes some other shape uses too.
    public let shared: Set<Int64>
    /// The other shapes (way ids) that hold a shared node.
    public let neighbours: Set<Int64>
    /// Mean `alt_abs` of the nodes that carry one (nil: all from the mesh).
    public let meanAlt: Double?

    public init(shapes picked: Set<Int64>, in doc: PatchDocument) {
        let ways = picked.union(Self.holes(of: picked, in: doc))
        let mine = Set(doc.ways.filter { ways.contains($0.id) }.flatMap(\.refs)).filter { doc.nodes[$0] != nil }
        let neighbours = Set(doc.ways.filter { !ways.contains($0.id) && !mine.isDisjoint(with: $0.refs) }.map(\.id))
        let shared = Set(doc.ways.filter { neighbours.contains($0.id) }.flatMap(\.refs)).intersection(mine)
        let alts = mine.sorted().compactMap { doc.nodes[$0]?.alt }
        self.ways = ways
        self.own = mine.subtracting(shared)
        self.shared = shared
        self.neighbours = neighbours
        meanAlt = alts.isEmpty ? nil : alts.reduce(0, +) / Double(alts.count)
    }

    /// The nodes Apply sets, sorted.
    public func targets(includeShared: Bool = true) -> [Int64] {
        (includeShared ? own.union(shared) : own).sorted()
    }

    /// The dialog's first line: "N shared nodes, M neighbouring shapes affected."
    public func summary(includeShared: Bool = true) -> String {
        func n(_ count: Int, _ word: String) -> String { "\(count.formatted()) \(word)\(count == 1 ? "" : "s")" }
        guard includeShared else {
            return "\(n(shared.count, "shared node")) left as they are; no neighbouring shapes affected."
        }
        return "\(n(shared.count, "shared node")), \(n(neighbours.count, "neighbouring shape")) affected."
    }

    public static func metres(_ value: Double, from unit: Unit) -> Double {
        unit == .feet ? value / feetPerMetre : value
    }

    public static func value(_ metres: Double, in unit: Unit) -> Double {
        unit == .feet ? metres * feetPerMetre : metres
    }

    /// The gap-ring ways `PatchShapeAssembly` pairs with the surfaces in
    /// `picked` (a nested surface is its own shape, never a hole here).
    static func holes(of picked: Set<Int64>, in doc: PatchDocument) -> Set<Int64> {
        var gaps: [[Int64]: Int64] = [:]
        for way in doc.ways where PatchShapeAssembly.isGapRing(way) { gaps[Array(way.refs.dropLast())] = way.id }
        guard !gaps.isEmpty else { return [] }
        return Set(PatchShapeAssembly.shapes(of: doc).filter { picked.contains($0.wayID) }
            .flatMap(\.holes).compactMap { gaps[$0] })
    }
}

extension PatchDocument {
    /// Set `alt` (metres MSL) on the plan's nodes (`setAlt`).
    public mutating func setShapeElevation(_ plan: PatchShapeElevation, alt: Double,
                                           includeShared: Bool = true) throws {
        try setAlt(plan.targets(includeShared: includeShared), alt: alt)
    }
}
