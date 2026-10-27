import Foundation

/// The per-step strip of one tile's Activity row (issue #825).
///
/// A tile's build reads as six steps, in this order:
/// Map data → Airports → Ground → Water → Imagery → Install, each waiting,
/// running or done (or skipped, failed, stopped), a finished step with its
/// time, and the running Airports step naming the airport and its stage in
/// plain words ("KSEA — shaping runways (65 %)").
///
/// This is the ONE event -> strip mapping of the Mac app; the Qt window's
/// twin is `Ortho4XP/src/O4_Step_Strip.py`. Both are pure (the caller
/// passes the time an event arrived) and both are tested against the same
/// fixture, `Ortho4XP/tests/fixtures/step_strip_cases.json`. The data is
/// what the engine already sends; there is no wire change.
public struct O4StepStrip: Equatable, Sendable {
    public enum State: String, Sendable {
        case waiting, running, done, skipped, failed, stopped
    }

    public struct Pill: Equatable, Sendable {
        public let key: String
        public let name: String
        public var state: State = .waiting
        var started: Double?
        var seconds: Double?
        var reused = false
    }

    public struct Segment: Equatable, Sendable {
        public let state: State
        public let text: String
    }

    /// (key, display name) in build order.
    public static let steps: [(key: String, name: String)] = [
        ("map_data", "Map data"),
        ("airports", "Airports"),
        ("ground", "Ground"),
        ("water", "Water"),
        ("imagery", "Imagery"),
        ("install", "Install"),
    ]

    /// Engine step key (wire `StepProgress.step_key`) -> step. Airport
    /// grading runs inside the `vector` step; its own events say so.
    public static let stepPills: [String: String] = [
        "vector": "map_data",
        "mesh": "ground",
        "masks": "water",
        "imagery": "imagery",
        "dsf": "imagery",
        "overlays": "install",
        "overlay": "install",
    ]

    /// An airport build's phase label -> its stage in plain words, matched
    /// by lower-case prefix. Mirror of `O4_Step_Strip.AIRPORT_STAGES`
    /// (`Ortho4XP/tests/test_step_strip.py` compares the two tables).
    public static let airportStages: [(prefix: String, words: String)] = [
        ("loading airport", "reading the airport"),
        ("loading apt.dat", "reading the airport"),
        ("partitioning the pack", "sorting the airport's shapes"),
        ("classifying", "reading buildings and structures"),
        ("building the planar map", "laying out the surfaces"),
        ("assembling pavement", "laying out runways"),
        ("building taxi", "laying out taxiways"),
        ("generating the law constraints", "setting the grading rules"),
        ("solving", "shaping runways"),
        ("emitting", "writing the airport patch"),
    ]
    public static let airportStageDefault = "grading"

    public static let glyphs: [State: String] = [
        .waiting: "○", .running: "●", .done: "✓",
        .skipped: "–", .failed: "✕", .stopped: "■",
    ]
    public static let separator = " → "
    static let nbsp = "\u{00A0}"

    public private(set) var pills: [Pill] = O4StepStrip.steps.map { Pill(key: $0.key, name: $0.name) }
    private var furthest = -1
    private var airportsTotal = 0
    private var airportsFinished: [String] = []
    private var airportLine = ""
    /// Built, failed or stopped: later news of this attempt is stale.
    private var ended = false

    public init() {}

    /// The plain-words stage of an airport build's progress label.
    public static func airportStage(_ label: String) -> String {
        let text = label.trimmingCharacters(in: .whitespaces).lowercased()
        return airportStages.first { text.hasPrefix($0.prefix) }?.words ?? airportStageDefault
    }

    /// `m:ss`, or `h:mm:ss` from an hour on (half-up, as the Qt twin).
    static func clock(_ seconds: Double) -> String {
        ProgressRowText.clock(floor(max(0, seconds) + 0.5))
    }

    // MARK: - Folding events

    /// Fold one engine event, which arrived at `now` (seconds). Anything
    /// but StepProgress, AutoPatchBegin, AutoPatchProgress, TileState and
    /// BuildDone is ignored, and so is everything after the tile was built,
    /// failed or stopped. A re-queued tile starts a new strip.
    public mutating func apply(_ event: O4Event, at now: Double) {
        guard !ended else { return }
        switch event {
        case .stepProgress(_, _, let stepKey, let label, _, _, _):
            let autoPatch = "auto-patch"
            let key = label == autoPatch || label.hasPrefix(autoPatch + " ")
                ? "airports" : Self.stepPills[stepKey]
            guard let key, let position = index(key) else { return }
            enter(position, at: now)
            if label.contains(" · reused"), pills[position].state == .running {
                pills[position].reused = true
            }
        case .autoPatchBegin(let airports, _, _):
            let airportsIndex = index("airports")!
            if enter(airportsIndex, at: now) || running == airportsIndex {
                airportsTotal = airports.count
            }
        case .autoPatchProgress(let airport, let done, let total, let label, let status, _, _, _):
            let airportsIndex = index("airports")!
            if running != airportsIndex, !enter(airportsIndex, at: now) { return }
            if status == "done" || status == "fail" {
                if !airportsFinished.contains(airport) { airportsFinished.append(airport) }
                airportLine = ""
                if airportsTotal > 0, airportsFinished.count >= airportsTotal {
                    finishRunning(at: now)
                }
                return
            }
            let percent = total > 0 ? 100 * done / total : 0
            let shown = Int(floor(min(max(percent, 0), 100) + 0.5))
            airportLine = "\(airport) — \(Self.airportStage(label)) (\(shown) %)"
        case .tileState(_, _, let state, let label, _, _, _):
            if state == "done" {
                finishBuild(at: now, ok: true)
            } else if state == "error" {
                finishBuild(at: now, ok: false)
            } else if label == "stopped" {
                stop(at: now)
            }
        case .buildDone(_, _, let ok, _, _, _, _, _):
            finishBuild(at: now, ok: ok)
        default:
            break
        }
    }

    /// The user stopped the tile: its running step is stopped, and the
    /// engine's late news of this attempt changes nothing.
    public mutating func stop(at now: Double) {
        guard !ended else { return }
        finishRunning(at: now, state: .stopped)
        ended = true
    }

    private func index(_ key: String) -> Int? {
        pills.firstIndex { $0.key == key }
    }

    private var running: Int? {
        pills.firstIndex { $0.state == .running }
    }

    private mutating func finishRunning(at now: Double, state: State = .done) {
        guard let index = running else { return }
        pills[index].state = state
        if state == .done, let started = pills[index].started {
            pills[index].seconds = max(0, now - started)
        }
        if pills[index].key == "airports" { airportLine = "" }
    }

    /// Step `index` is running: the one before it is done, any passed over
    /// are skipped. News of a step already behind is ignored.
    @discardableResult
    private mutating func enter(_ index: Int, at now: Double) -> Bool {
        guard index > furthest else { return false }
        finishRunning(at: now)
        for passed in (furthest + 1)..<index {
            pills[passed].state = .skipped
        }
        pills[index].state = .running
        pills[index].started = now
        pills[index].seconds = nil
        furthest = index
        return true
    }

    private mutating func finishBuild(at now: Double, ok: Bool) {
        ended = true
        guard ok else {
            if running == nil, furthest >= 0 {
                // The step that ended the build had finished (an airport
                // that failed after the others): it is the one that failed.
                pills[furthest].state = .running
            }
            finishRunning(at: now, state: .failed)
            return
        }
        finishRunning(at: now)
        for index in pills.indices where pills[index].state == .waiting {
            // The tile is written out whether or not an overlay step ran.
            pills[index].state = pills[index].key == "install" ? .done : .skipped
        }
        furthest = pills.count - 1
    }

    // MARK: - What a row shows

    /// One segment per step, in order. Words of one step are joined by
    /// no-break spaces, so a wrapping row breaks only between steps (or
    /// inside the airport line).
    public var segments: [Segment] {
        let nbsp = Self.nbsp
        return pills.map { pill in
            var text = (Self.glyphs[pill.state] ?? "") + nbsp
                + pill.name.replacingOccurrences(of: " ", with: nbsp)
            if pill.key == "airports", pill.state == .running {
                if airportsTotal > 1 {
                    text += nbsp + "\(airportsFinished.count)/\(airportsTotal)"
                }
                if !airportLine.isEmpty { text += " · " + airportLine }
            }
            if pill.state == .done, pill.reused {
                text += nbsp + "reused"
            } else if pill.state == .done, let seconds = pill.seconds {
                text += nbsp + Self.clock(seconds)
            }
            return Segment(state: pill.state, text: text)
        }
    }

    /// The whole strip as one plain line (the segments, arrows between).
    public var text: String {
        segments.map(\.text).joined(separator: Self.separator)
    }
}
