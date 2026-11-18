import Foundation

/// Runs work once the calls to `run` have stopped for `seconds` (#2162:
/// a burst of disk-budget changes measures the data folder once). A
/// later call cancels the earlier one, including work already running,
/// which checks `Task.isCancelled` before it shows a result.
@MainActor
public final class O4Settle {
    public let seconds: Double
    private var task: Task<Void, Never>?

    public init(seconds: Double) { self.seconds = seconds }

    public func run(_ work: @escaping @MainActor () async -> Void) {
        task?.cancel()
        task = Task { [seconds] in
            try? await Task.sleep(for: .seconds(seconds))
            guard !Task.isCancelled else { return }
            await work()
        }
    }
}
