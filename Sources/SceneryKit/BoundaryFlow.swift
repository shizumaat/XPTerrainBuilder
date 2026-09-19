import Foundation

/// Whoever can start the boundary preflight — `OrthoEngineClient` in the
/// app, a fake in the tests. The flow is the same either way.
public protocol O4BoundaryPreflightSender: AnyObject {
    /// `nil` in the completion = the preflight never started (an engine
    /// older than protocol 1.8 answers ok=false to an unknown command).
    func requestBoundaryAirports(tiles: [O4TileRef],
                                 completion: @escaping @Sendable (Int?) -> Void)
}

extension OrthoEngineClient: O4BoundaryPreflightSender {}

/// What the front end does once the preflight has answered.
public enum O4BoundaryOutcome: Sendable, Equatable {
    /// Enqueue now. `policy` is the `boundary_policy` keyword (nil = leave
    /// it out entirely and let the engine resolve it from cfg).
    case enqueue(policy: String?, addTiles: [O4TileRef])
    /// Ask the user: ONE sheet for the whole press.
    case ask(airports: [O4BoundaryAirport], addTiles: [O4TileRef],
             defaultChoice: String)
}

/// The boundary preflight's state machine (protocol 1.8, spec
/// insets-follow-patch-set-spec.md §C.7). One per build press:
///
///   1. the front end sends `boundary_airports` and feeds the command's own
///      reply to `started(requestID:)`,
///   2. every `BoundaryAirportsReady` event goes to `ready(_:)` — one whose
///      id is not this press's is IGNORED,
///   3. the first `.outcome` settles the press; anything after it is
///      ignored, so a late event cannot enqueue a second time.
///
/// The event can reach the front end before the command's reply does; the
/// flow then HOLDS it (`.waiting`) rather than guess, and settles as soon
/// as the id is known.
public struct O4BoundaryFlow: Sendable, Equatable {
    public enum Step: Sendable, Equatable {
        /// Nothing to do yet — the id or the event is still missing.
        case waiting
        /// Act on this.
        case outcome(O4BoundaryOutcome)
        /// Stale: a different press's event, or this press is settled.
        case ignored
    }

    private var requestID: Int?
    private var early: O4BoundaryAirportsReady?
    private var settled = false

    public init() {}

    /// Is this press still waiting on the engine?
    public var isSettled: Bool { settled }

    /// The `boundary_airports` command's own reply.
    public mutating func started(requestID: Int?) -> Step {
        guard !settled else { return .ignored }
        guard let requestID else {
            // Older engine / refused command: degrade to exactly what the
            // app did before 1.8 — enqueue, no policy, no dialog.
            settled = true
            return .outcome(.enqueue(policy: nil, addTiles: []))
        }
        self.requestID = requestID
        if let early {
            self.early = nil
            return ready(early)
        }
        return .waiting
    }

    /// One `BoundaryAirportsReady` event.
    public mutating func ready(_ ready: O4BoundaryAirportsReady) -> Step {
        guard !settled else { return .ignored }
        guard let requestID else {
            early = ready
            return .waiting
        }
        guard requestID == ready.requestID else { return .ignored }
        let outcome = Self.outcome(for: ready)
        if case .enqueue = outcome { settled = true }
        return .outcome(outcome)
    }

    /// The preflight took too long, or the engine failed outright: the
    /// preflight can never be the thing that stops a build (spec §C.7).
    public mutating func giveUp() -> Step {
        guard !settled else { return .ignored }
        settled = true
        return .outcome(.enqueue(policy: nil, addTiles: []))
    }

    /// The user answered, or abandoned the press.
    public mutating func close() { settled = true }

    /// The ruling in one function: error or nothing to ask about ⇒ enqueue
    /// with no policy; a remembered answer ⇒ apply it without asking;
    /// otherwise ⇒ ask.
    public static func outcome(for ready: O4BoundaryAirportsReady) -> O4BoundaryOutcome {
        guard ready.error.isEmpty, !ready.airports.isEmpty else {
            return .enqueue(policy: nil, addTiles: [])
        }
        switch ready.remembered {
        case "neighbour": return .enqueue(policy: "neighbour", addTiles: ready.addTiles)
        case "skip": return .enqueue(policy: "skip", addTiles: [])
        default:
            return .ask(airports: ready.airports, addTiles: ready.addTiles,
                        defaultChoice: ready.defaultChoice)
        }
    }
}
