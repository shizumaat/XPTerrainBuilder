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
            guard let done = try? await client.storageAutoClean() else { return }
            if done.ran == true, done.files > 0 {
                self?.console.append(
                    "Storage cleanup freed \(Library.size(done.freedBytes)) in \(done.files) file(s) (logs/storage.log).")
            }
            // The disk budget's warning (RULINGS 2026-11-10c (2) / 10d (2)).
            let warning = O4StorageText.cleanupWarning(done)
            if !warning.isEmpty { self?.console.append(warning) }
        }
    }

    /// Convert existing tiles' Measure, by itself (owner 2026-11-12T19:08Z):
    /// at the engine's start and after each Convert step, the kept measure
    /// is shown and, when Custom Scenery holds per-tile packs (or tiles to
    /// adopt again) and none is kept or it changed since, one starts in the
    /// background (`WorldMigrateRun.startAuto`).
    func startAutoMeasure() {
        guard engineCapabilities.supports(O4EngineCapabilities.worldMeasure),
              let context = libraryContext() else { return }
        worldMigrate.startAuto(client: context.client, sceneryDir: context.sceneryDir)
    }
}
