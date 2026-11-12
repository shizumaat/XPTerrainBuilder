import Foundation
import SceneryKit

extension BuildModel {
    /// The world switch's config key (#1992 spec §7).
    static let imageryOnDemandKey = "imagery_on_demand"

    /// Follow X-Plane when the world switch is on (and the user has not
    /// stopped it), stop when it is off (#1992 P4). Run when the engine
    /// session starts and when the switch changes in Settings; the engine
    /// reads the follow settings itself and finds the on-demand tiles.
    func syncImageryFollow() {
        let enabled = configValue(for: Self.imageryOnDemandKey) == .bool(true)
        imageryFollow.enabled = enabled
        guard let context = libraryContext() else { return }
        if enabled, !imageryFollow.running, !imageryFollow.stoppedByUser {
            startImageryFollow(context.client, workingDir: context.workingDir, ifEnabled: true)
        } else if !enabled, imageryFollow.running {
            context.client.stopImageryFollow()
        }
    }

    /// The follow line's "Reload scenery" for a pending reload offer
    /// (#2019): sent only on this click. Python:
    /// `O4_Qt_GUI._reload_scenery`.
    func reloadScenery() {
        libraryContext()?.client.reloadScenery()
    }

    /// The follow line's Follow X-Plane / Stop Following.
    func toggleImageryFollow(start: Bool) {
        guard let context = libraryContext() else { return }
        imageryFollow.stoppedByUser = !start
        if start {
            startImageryFollow(context.client, workingDir: context.workingDir, ifEnabled: false)
        } else {
            context.client.stopImageryFollow()
        }
    }

    private func startImageryFollow(_ client: OrthoEngineClient, workingDir: String, ifEnabled: Bool) {
        client.startImageryFollow(workingDir: workingDir, ifEnabled: ifEnabled) { status in
            Task { @MainActor [weak self] in
                guard let self, let status else { return }
                self.imageryFollow.running = status == "started" || status == "running"
            }
        }
    }

    /// "Always keep full resolution" / "Let it go low-res again" for one
    /// tile (engine `imagery_pin`), then a rescan so the tile pane and the
    /// Library show the pin. Answers one sentence for the user.
    func setImageryPinned(_ coord: TileCoord, _ pinned: Bool) async -> String {
        guard let context = libraryContext() else { return "The engine is not running." }
        do {
            let done = try await context.client.imageryPin(
                lat: coord.lat, lon: coord.lon, pinned: pinned, workingDir: context.workingDir)
            console.append(O4OnDemandText.pinDone(done))
            rescan()
            return O4OnDemandText.pinDone(done)
        } catch {
            return "\(error)"
        }
    }
}
