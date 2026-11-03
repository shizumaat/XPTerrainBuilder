import Foundation
import SceneryKit

extension BuildModel {
    /// Settings ▸ Storage's automatic cleanup (#1724), run when the engine
    /// session starts and after each run ends. The engine reads the two
    /// settings (off by default), does nothing when both are off, and
    /// refuses while a build runs; a freed amount is one console line, and
    /// every deletion is in the data folder's logs/storage.log.
    func runStorageAutoClean() {
        guard let client = libraryContext()?.client else { return }
        Task { @MainActor [weak self] in
            guard let done = try? await client.storageAutoClean(),
                  done.ran == true, done.files > 0 else { return }
            self?.console.append(
                "Storage cleanup freed \(Library.size(done.freedBytes)) in \(done.files) file(s) (logs/storage.log).")
        }
    }
}
