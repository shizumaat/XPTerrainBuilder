import Foundation

/// Thread-safe holder for "which packs does the user care about right now".
/// The UI updates it as the tile selection changes; analysis workers consult
/// it when pulling the next pack, so a selection made mid-scan jumps the
/// queue without restarting anything.
public final class PriorityBox: @unchecked Sendable {
    private let lock = NSLock()
    private var names: Set<String> = []

    public init() {}

    public var current: Set<String> {
        lock.lock(); defer { lock.unlock() }
        return names
    }

    public func update(_ new: Set<String>) {
        lock.lock(); defer { lock.unlock() }
        names = new
    }
}

/// Runs `worker` over every pack on all cores, like concurrentPerform, but
/// pulls work from a shared queue that serves prioritized packs first —
/// priority is re-read on every pull, so it can change while running.
func forEachPackPrioritized(
    _ packs: [SceneryPack],
    priority: (@Sendable () -> Set<String>)?,
    worker: @Sendable (Int) -> Void
) {
    guard !packs.isEmpty else { return }
    let queue = WorkQueue(names: packs.map { $0.name }, priority: priority)
    let workers = min(packs.count, max(2, ProcessInfo.processInfo.activeProcessorCount))
    DispatchQueue.concurrentPerform(iterations: workers) { _ in
        while let index = queue.next() {
            worker(index)
        }
    }
}

/// Mutex-guarded mutable state for aggregating results from parallel workers
/// without Sendable-capture warnings.
public final class LockedBox<T>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: T

    public init(_ value: T) { self.value = value }

    @discardableResult
    public func withLock<R>(_ body: (inout T) -> R) -> R {
        lock.lock(); defer { lock.unlock() }
        return body(&value)
    }
}

private final class WorkQueue: @unchecked Sendable {
    private let lock = NSLock()
    private var pending: [Int]        // indices into names, in original order
    private let names: [String]
    private let priority: (@Sendable () -> Set<String>)?

    init(names: [String], priority: (@Sendable () -> Set<String>)?) {
        self.names = names
        self.pending = Array(names.indices)
        self.priority = priority
    }

    func next() -> Int? {
        lock.lock(); defer { lock.unlock() }
        guard !pending.isEmpty else { return nil }
        if let wanted = priority?(), !wanted.isEmpty,
           let at = pending.firstIndex(where: { wanted.contains(names[$0]) }) {
            return pending.remove(at: at)
        }
        return pending.removeFirst()
    }
}
