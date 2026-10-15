import Foundation

/// What one edit (or its undo) touched in the patch document. Nodes whose
/// position or elevation changed go in `nodes`; ways whose ref list changed
/// (or that were added or removed) go in `ways` and set `topology`. A view
/// rebuilds the shapes that use any listed node, and re-triangulates the
/// listed ways.
struct PatchChange: Equatable {
    var nodes: Set<Int64> = []
    var ways: Set<Int64> = []
    var topology = false
    /// A new document was loaded or reverted: rebuild everything.
    var everything = false

    static let all = PatchChange(everything: true)
}
