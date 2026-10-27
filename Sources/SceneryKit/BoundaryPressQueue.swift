import Foundation

/// The build presses waiting on the boundary preflight, in press order.
///
/// ONE preflight runs at a time (each press gets its own ask, RULINGS
/// 2026-09-18b/18i): a press made while one is in flight waits here and
/// starts its own preflight when the one ahead settles. While a build
/// runs, the Queue button therefore stays live — a press joins the line at
/// once instead of the button going grey until the engine answers (the
/// 1.0.433 report: Queue disabled while a 100-airport tile solved). With
/// no build running a press while one is in flight is still refused: it
/// would start a second run for the same tiles.
public struct O4BoundaryPressQueue<Press>: Sendable where Press: Sendable {
    private var inFlight = false
    private var waiting: [Press] = []

    public init() {}

    /// Is a preflight in flight?
    public var isPreflighting: Bool { inFlight }

    /// Presses waiting behind the one in flight.
    public var waitingCount: Int { waiting.count }

    /// May the Build/Queue button take a press now?
    public static func acceptsPress(isPreflighting: Bool, isBuilding: Bool) -> Bool {
        !isPreflighting || isBuilding
    }

    /// A press: returns it when its preflight starts NOW, nil when it
    /// waits behind the one in flight.
    public mutating func submit(_ press: Press) -> Press? {
        guard inFlight else {
            inFlight = true
            return press
        }
        waiting.append(press)
        return nil
    }

    /// The preflight in flight settled (enqueued, cancelled or gave up):
    /// the next waiting press, whose preflight starts now, or nil.
    public mutating func settle() -> Press? {
        guard !waiting.isEmpty else {
            inFlight = false
            return nil
        }
        return waiting.removeFirst()
    }
}
