import Foundation

/// One undoable edit of a `PatchDocument` as the difference between the
/// document before and after it (spec §4: ⌘Z / ⇧⌘Z, a drag is one step).
/// Holds only the nodes that changed; the way list and the node order are
/// kept only when they changed (copy-on-write buffers the documents already
/// own), so a 30k-node patch's history stays small.
public struct PatchEditStep: Sendable {
    /// A node's value before and after (nil = absent on that side).
    public struct NodeSwap: Equatable, Sendable {
        public let before: PatchNode?
        public let after: PatchNode?
    }

    public let nodes: [Int64: NodeSwap]
    let waysBefore: [PatchWay]?
    let waysAfter: [PatchWay]?
    let orderBefore: [Int64]?
    let orderAfter: [Int64]?

    /// Nodes present on both sides whose position or elevation changed.
    public let movedNodes: Set<Int64>
    /// Ways whose ref list changed, or that were added or removed.
    public let changedWays: Set<Int64>
    /// Any way's refs or the node set changed.
    public var topology: Bool { waysBefore != nil || orderBefore != nil }
    public var isEmpty: Bool { nodes.isEmpty && !topology }

    public init(from before: PatchDocument, to after: PatchDocument) {
        var swaps: [Int64: NodeSwap] = [:]
        for (id, node) in after.nodes where before.nodes[id] != node {
            swaps[id] = NodeSwap(before: before.nodes[id], after: node)
        }
        let orderDiffers = before.nodeOrder != after.nodeOrder
        if orderDiffers {  // only a delete or a merge removes a node
            for (id, node) in before.nodes where after.nodes[id] == nil {
                swaps[id] = NodeSwap(before: node, after: nil)
            }
        }
        nodes = swaps
        movedNodes = Set(swaps.compactMap { $0.value.before != nil && $0.value.after != nil ? $0.key : nil })
        let waysDiffer = before.ways != after.ways
        waysBefore = waysDiffer ? before.ways : nil
        waysAfter = waysDiffer ? after.ways : nil
        orderBefore = orderDiffers ? before.nodeOrder : nil
        orderAfter = orderDiffers ? after.nodeOrder : nil
        changedWays = waysDiffer ? Self.changedWayIDs(before.ways, after.ways) : []
    }

    private static func changedWayIDs(_ a: [PatchWay], _ b: [PatchWay]) -> Set<Int64> {
        let refsA = Dictionary(a.map { ($0.id, $0.refs) }, uniquingKeysWith: { x, _ in x })
        let refsB = Dictionary(b.map { ($0.id, $0.refs) }, uniquingKeysWith: { x, _ in x })
        return Set(refsA.keys).union(refsB.keys).filter { refsA[$0] != refsB[$0] }
    }
}

extension PatchDocument {
    /// Apply a step forward (redo) or backward (undo).
    public mutating func apply(_ step: PatchEditStep, reversed: Bool = false) {
        for (id, swap) in step.nodes { nodes[id] = reversed ? swap.before : swap.after }
        if let ways = reversed ? step.waysBefore : step.waysAfter { self.ways = ways }
        if let order = reversed ? step.orderBefore : step.orderAfter { nodeOrder = order }
        reindex()
    }
}
