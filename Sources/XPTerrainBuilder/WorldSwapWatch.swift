import SceneryKit

/// When a World or flight job puts a tile into the World pack, the Build
/// map rescans: the tile's World state changed and its build (records,
/// patches) is now ours to show — the patch view and editor included
/// (owner 2026-11-12T22:19Z: a tile a flight had just built showed no
/// patch view or editor when zoomed in). The build itself refreshes
/// through its BuildDone and RunDone; the swap comes after them. The rule is one rule in both apps
/// (Qt: `O4_World_Swap_Watch.SwapWatch`, twinned on
/// `tests/fixtures/world_swap_watch_cases.json`).
struct WorldSwapWatch {
    private var swapped: Set<String> = []
    private var lastSwap: [String] = []

    /// A `FlightStatus`: true when a job reached "swapped" that was not
    /// swapped in the last status.
    mutating func flightStatus(_ status: O4FlightStatus) -> Bool {
        let now = Set(status.jobs.filter { $0.state == Self.swappedState }
            .map { "\($0.lat),\($0.lon)" })
        defer { swapped = now }
        return !now.subtracting(swapped).isEmpty
    }

    /// A `WorldStatus`: true when it names a swap the last one did not.
    mutating func worldStatus(_ status: O4WorldStatus) -> Bool {
        defer { lastSwap = status.lastSwap }
        return !status.lastSwap.isEmpty && status.lastSwap != lastSwap
    }

    static let swappedState = "swapped"
}
