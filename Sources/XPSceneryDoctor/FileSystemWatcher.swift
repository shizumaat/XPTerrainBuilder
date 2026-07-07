import Foundation

/// Debounced DispatchSource watcher over directories and files: fires
/// `onChange` once per burst of filesystem activity. Directories report
/// immediate-children changes (add/remove/rename of pack folders); watched
/// FILES that get atomically replaced (scenery_packs.ini) re-arm on the new
/// inode after the delete/rename event.
@MainActor
final class FileSystemWatcher {
    private let paths: [String]
    private let debounceSeconds: Double
    private let onChange: () -> Void
    private var sources: [String: DispatchSourceFileSystemObject] = [:]
    private var pending: Task<Void, Never>?

    init(paths: [String], debounceSeconds: Double = 2, onChange: @escaping () -> Void) {
        self.paths = paths
        self.debounceSeconds = debounceSeconds
        self.onChange = onChange
    }

    func start() {
        for path in paths { arm(path) }
    }

    func stop() {
        pending?.cancel()
        for source in sources.values { source.cancel() }
        sources = [:]
    }

    private func arm(_ path: String) {
        sources[path]?.cancel()
        sources[path] = nil
        let fd = open(path, O_EVTONLY)
        guard fd >= 0 else { return } // path absent; re-armed if it appears via a parent event
        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fd, eventMask: [.write, .delete, .rename], queue: .main)
        source.setEventHandler { [weak self] in
            guard let self else { return }
            let flags = source.data
            self.bump()
            if flags.contains(.delete) || flags.contains(.rename) {
                // Atomic saves replace the inode — watch the new file.
                source.cancel()
                self.sources[path] = nil
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
                    self?.arm(path)
                }
            }
        }
        source.setCancelHandler { close(fd) }
        source.resume()
        sources[path] = source
    }

    private func bump() {
        pending?.cancel()
        pending = Task { @MainActor [weak self] in
            guard let self else { return }
            try? await Task.sleep(for: .seconds(self.debounceSeconds))
            guard !Task.isCancelled else { return }
            self.onChange()
        }
    }
}
