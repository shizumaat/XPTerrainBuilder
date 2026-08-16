import Foundation
import SwiftUI
import SceneryKit
import os

private let appLog = Logger(subsystem: "com.novemberlima.XPTerrainBuilder", category: "app")

/// High-frequency progress state, isolated from AnalysisController so a
/// scan tick can't invalidate the map canvas — only the small views that
/// actually render progress observe this.
@MainActor
final class ProgressModel: ObservableObject {
    /// (probed, total) while the installation scan runs — drives the
    /// determinate loading bar. nil outside a scan.
    @Published var scanProgress: (done: Int, total: Int)?
}

/// Owns the scanned X-Plane installation and the map's view of it: the pack
/// list, the derived map overlays, the camera, and the live watcher that
/// keeps all of it in step with Custom Scenery.
@MainActor
final class AnalysisController: ObservableObject {
    @AppStorage(PrefKeys.xplanePath) var xplanePath: String = ""

    /// See ProgressModel — deliberately NOT @Published here.
    let progress = ProgressModel()

    @Published var errorMessage: String?

    // Map: the scanned installation (packs with tiles/airports/status) and
    // the user's tile selection.
    //
    // The camera and canvas size are ViewState objects OWNED here but NOT
    // observed: only MapCanvasView subscribes, so a drag frame redraws the
    // canvas alone. If the main window held them as @StateObject, every
    // camera tick would re-evaluate the whole window body (the beachball).
    let mapCamera = ViewState(MapCamera())
    let mapCanvasSize = ViewState(CGSize.zero)
    /// Packs visible in the map viewport, debounced from camera movement.
    @Published var viewportPacks: [SceneryPack] = []
    private var viewportTask: Task<Void, Never>?

    @Published var installationPacks: [SceneryPack] = []
    /// The last completed full scan.
    private var lastScan: Installation?
    /// Live watcher on Custom Scenery, the Disabled folder and
    /// scenery_packs.ini: external adds/removes/renames trigger a rescan
    /// (which reconciles the ini), external ini edits refresh statuses.
    private var watcher: FileSystemWatcher?
    /// Our own ini writes fire the watcher too — events inside this window
    /// (or while we're scanning) are ours and get ignored.
    private var watcherCooldownUntil = ContinuousClock.now
    /// Precomputed draw/query structures — rebuilt only when the scan
    /// changes, never per frame.
    @Published var mapOverlays = MapOverlays.empty
    @Published var isScanningInstallation = false
    /// X-Plane's default airports (Global Airports), as the ENGINE's index
    /// reports them: BuildModel asks for it over the `airport_index`
    /// command and hands the result here (setGlobalAirports). Kept in
    /// memory so a rescan re-derives the marks without re-reading anything.
    private var globalAirports: [GlobalAirport] = []

    var rootURL: URL? {
        guard !xplanePath.isEmpty else { return nil }
        return URL(fileURLWithPath: xplanePath, isDirectory: true)
    }

    // MARK: - Installation scan (map data)

    /// A refresh requested while a scan is in flight; runs when it finishes.
    /// (An in-flight scan read the ini before whatever prompted the request,
    /// so its results can be stale — the follow-up scan settles things.)
    private var pendingRefresh = false

    func refreshInstallation() {
        guard let root = rootURL else { return }
        guard !isScanningInstallation else {
            pendingRefresh = true
            return
        }
        isScanningInstallation = true
        let previousPacks = lastScan?.packs ?? []
        // With nothing on screen yet, the scan streams partial results so
        // the map populates live; once anything is showing (an optimistic
        // load or a prior scan), partials would shrink the list mid-rescan.
        let nothingShowing = installationPacks.isEmpty
        // The gray default-airport marks, as the engine's index last
        // reported them (setGlobalAirports). An index that arrives AFTER
        // this scan installs itself on the finished overlays there.
        let globals = globalAirports
        Task { [weak self] in
            let (installation, overlays, reconciliation) = await Task.detached(priority: .userInitiated) {
                // Persisted scenery index: after the first launch, unchanged
                // packs (by content signature) skip apt.dat parsing and DSF
                // reads — the rescan touches file metadata only.
                let probeCache = SceneryIndexCache.load(for: root)
                // Optimistic launch: rebuild last session's full pack list
                // straight from the cache (no per-pack disk walks) and show
                // it immediately; the scan below revalidates and replaces
                // it, catching anything added, removed or changed.
                var showedCachedPacks = false
                if nothingShowing, !probeCache.isEmpty {
                    let cachedPacks = InstallationScanner(root: root).packsFromCache(probeCache)
                    if !cachedPacks.isEmpty {
                        showedCachedPacks = true
                        let overlays = MapOverlays(packs: cachedPacks)
                            .applyingExactMarkers(InstallationScanner.packMarkers(for: cachedPacks))
                            .withDefaultAirports(globals)
                        Task { @MainActor [weak self] in
                            guard let self, self.isScanningInstallation,
                                  self.installationPacks.isEmpty else { return }
                            self.installationPacks = cachedPacks
                            self.mapOverlays = overlays
                            self.scheduleViewportUpdate()
                        }
                    }
                }
                let streamPartials = nothingShowing && !showedCachedPacks
                var (installation, updatedCache) = InstallationScanner(root: root).scan(
                    cache: probeCache,
                    progress: { done, total in
                        Task { @MainActor [weak self] in
                            self?.progress.scanProgress = (done, total)
                        }
                    },
                    onPartial: !streamPartials ? nil : { partial in
                        // Populate the map live as packs are discovered.
                        // Overlays are built here on the worker thread; the
                        // completed scan below supersedes any queued partial.
                        let overlays = MapOverlays(packs: partial)
                            .applyingExactMarkers(InstallationScanner.packMarkers(for: partial))
                            .withDefaultAirports(globals)
                        Task { @MainActor [weak self] in
                            guard let self, self.isScanningInstallation else { return }
                            self.installationPacks = partial
                            self.mapOverlays = overlays
                            self.scheduleViewportUpdate()
                        }
                    }
                )
                SceneryIndexCache.save(updatedCache, for: root)
                // Bring scenery_packs.ini in line with what is ACTUALLY on
                // disk (X-Plane only does this at its own next launch). If
                // the ini changed, statuses/ranks the scan derived from the
                // OLD ini are stale — re-derive them cheaply.
                let reconciliation = PackActionService(root: root).reconcile(
                    installedPacks: installation.packs, previousPacks: previousPacks)
                if reconciliation.changed {
                    let service = PackActionService(root: root)
                    let order = service.iniOrder()
                    let statuses = service.iniStatuses()
                    var packs = installation.packs
                    for i in packs.indices where packs[i].isInstalled {
                        packs[i].iniIndex = order[packs[i].name]
                        packs[i].status = (statuses[packs[i].name] ?? true) ? .enabled : .disabled
                    }
                    installation = installation.replacingPacks(packs)
                }
                return (installation,
                        MapOverlays(packs: installation.packs)
                            .applyingExactMarkers(installation.packMarkers)
                            .withDefaultAirports(globals),
                        reconciliation)
            }.value
            guard let self else { return }
            if reconciliation.changed {
                // Our own write — the watcher must not bounce it back.
                self.watcherCooldownUntil = ContinuousClock.now + .seconds(4)
                appLog.notice("ini reconciled: +\(reconciliation.added.count) added, -\(reconciliation.removed.count) removed, \(reconciliation.renamed.count) renamed")
            }
            if let writeError = reconciliation.writeError {
                self.errorMessage = "Could not update scenery_packs.ini: \(writeError)"
            }
            self.lastScan = installation
            self.installationPacks = installation.packs
            self.mapOverlays = overlays
            self.isScanningInstallation = false
            self.progress.scanProgress = nil
            self.scheduleViewportUpdate()
            self.startWatchingIfNeeded()
            if self.pendingRefresh {
                self.pendingRefresh = false
                self.refreshInstallation()
            }
        }
    }

    /// Take delivery of X-Plane's default airports from the engine's index
    /// (BuildModel's `airport_index` command). The list is stored for the
    /// scans — all three of their publish paths install it — and the marks
    /// are re-derived for the CURRENT overlays right here, so an index that
    /// lands after a finished scan still shows up on the map.
    func setGlobalAirports(_ airports: [GlobalAirport]) {
        globalAirports = airports
        mapOverlays = mapOverlays.withDefaultAirports(airports)
        scheduleViewportUpdate()
    }

    /// Watch Custom Scenery, the Disabled folder and scenery_packs.ini for
    /// EXTERNAL changes (Finder deletes/adds/renames, X-Plane rewriting the
    /// ini). Events debounce into the normal rescan, whose reconcile step
    /// then repairs the ini. Our own writes are filtered by the cooldown
    /// and the scanning flag.
    private func startWatchingIfNeeded() {
        guard watcher == nil, let root = rootURL else { return }
        let service = PackActionService(root: root)
        let watched = FileSystemWatcher(paths: [
            root.appendingPathComponent("Custom Scenery").path,
            service.disabledFolderURL.path,
            root.appendingPathComponent("Custom Scenery/scenery_packs.ini").path,
        ]) { [weak self] in
            guard let self else { return }
            guard !self.isScanningInstallation,
                  ContinuousClock.now >= self.watcherCooldownUntil else { return }
            appLog.notice("filesystem change detected — rescanning Custom Scenery")
            self.refreshInstallation()
        }
        watched.start()
        watcher = watched
    }

    /// Debounced (120 ms) recompute of the packs visible in the map window.
    /// Called from the canvas as the camera moves; never runs in a render.
    func scheduleViewportUpdate() {
        viewportTask?.cancel()
        let cam = mapCamera.value
        let size = mapCanvasSize.value
        let overlays = mapOverlays
        viewportTask = Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(120))
            guard !Task.isCancelled, size.width > 0 else { return }
            let halfW = Double(size.width) / 2 / cam.scale
            let halfH = Double(size.height) / 2 / cam.scale
            let yCenter = MapCamera.mercatorY(lat: cam.centerLat)
            let packs = overlays.packs(inViewport: (
                minLon: cam.centerLon - halfW, maxLon: cam.centerLon + halfW,
                minLat: MapCamera.latitude(mercatorY: yCenter - halfH),
                maxLat: MapCamera.latitude(mercatorY: yCenter + halfH)
            ))
            self?.viewportPacks = packs.sorted { $0.name.lowercased() < $1.name.lowercased() }
        }
    }

    /// Zoom the map to a pack's coverage — used by the toolbar search.
    /// Airports first: an airport point is always right, while a tile-bbox
    /// fit spans the ocean for packs that ship stray tiles (the CYHZ +44+044
    /// case).
    func zoomToPack(_ pack: SceneryPack) {
        var cam = mapCamera.value
        if let airport = pack.airports.values.first {
            cam.centerLon = airport.longitude
            cam.centerLat = airport.latitude
            cam.scale = max(cam.scale, 60)
        } else {
            let tiles = pack.tiles.compactMap { TileMath.parse($0) }
            guard !tiles.isEmpty else { return }
            let lats = tiles.map { Double($0.lat) }, lons = tiles.map { Double($0.lon) }
            cam.centerLat = (lats.min()! + lats.max()! + 1) / 2
            cam.centerLon = (lons.min()! + lons.max()! + 1) / 2
            let spanLon = max(lons.max()! - lons.min()! + 1, 2)
            let spanLat = max(lats.max()! - lats.min()! + 1, 2)
            cam.scale = min(700 / spanLon, 400 / spanLat, 120)
        }
        cam.clamp(in: mapCanvasSize.value)
        mapCamera.value = cam
        scheduleViewportUpdate()
    }
}
