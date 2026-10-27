import Foundation
import SwiftUI
import CoreGraphics
import ImageIO
import QuartzCore
import SceneryKit
import os

private let imageryLog = Logger(subsystem: "com.novemberlima.XPTerrainBuilder", category: "imagery")

/// One imagery layer the map can display live: an engine source's
/// preview (`imagery_sources`, #1345). The engine builds the URL template
/// from its own request builders — TMS, WMTS and WMS (EPSG:3857) alike —
/// so this app never parses a .lay file or composes a provider URL.
struct ImageryProviderSpec: Equatable {
    let code: String
    let preview: O4ImageryPreview
    let maxZL: Int

    init(code: String, preview: O4ImageryPreview) {
        self.code = code
        self.preview = preview
        // Absent max_zl means the source declares NO ceiling (the engine
        // will build it at any ZL) — preview up to the fetch cap.
        self.maxZL = preview.maxZL ?? 21
    }

    var referer: String? { preview.referer.isEmpty ? nil : preview.referer }

    /// Matches the engine's request UA (O4_Imagery_Utils.user_agent_generic),
    /// used for commercial providers whose .lay files fake browser headers.
    static let userAgent =
        "Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0"

    /// Honest, app-identifying UA. OpenStreetMap's tile usage policy
    /// requires this and BLOCKS generic browser UAs coming from apps —
    /// faking Firefox against tile.openstreetmap.org gets the "Access
    /// blocked" tile served instead of imagery.
    static let appUserAgent: String = {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString")
            as? String ?? "1.0"
        return "XPTerrainBuilder/\(version) (X-Plane scenery builder; macOS)"
    }()

    /// The UA to send for this provider: honest for OSM (policy), the
    /// engine's browser UA elsewhere.
    var requestUserAgent: String {
        code == "OSM" ? Self.appUserAgent : Self.userAgent
    }

    /// The engine's template expanded for one tile
    /// (`O4_Imagery_Sources.expand_preview`).
    func url(z: Int, x: Int, y: Int) -> URL? {
        preview.url(z: z, x: x, y: y).flatMap { URL(string: $0) }
    }
}

/// Live map imagery, ported from the engine's Qt map: fetches webmercator
/// tiles for the selected build provider (OSM as base fallback), caches
/// them in memory and on disk — the same Previews/livemap/<code>/<z>/<x>_<y>.jpg
/// layout under the data root, so the two GUIs share downloads.
@MainActor
final class ImageryModel: ObservableObject {
    /// Bumped whenever a tile lands; the map canvas observes this.
    @Published private(set) var generation = 0

    struct TileKey: Hashable {
        let code: String
        let z: Int, x: Int, y: Int
    }

    /// A combined provider (.comb): ordered member layers, first match by
    /// extent wins, the last line is the global base layer.
    struct CombinedSpec: Equatable {
        struct Member: Equatable {
            let code: String
            /// Extent bbox (lon/lat) from the .ext's mask_bounds; nil = global.
            let bbox: (minLon: Double, minLat: Double, maxLon: Double, maxLat: Double)?

            static func == (lhs: Member, rhs: Member) -> Bool {
                lhs.code == rhs.code && lhs.bbox?.minLon == rhs.bbox?.minLon
                    && lhs.bbox?.minLat == rhs.bbox?.minLat
            }
        }
        let code: String
        let members: [Member]
    }

    private(set) var active: ImageryProviderSpec?
    private(set) var activeCombined: CombinedSpec?
    /// The source shown before the last switch, kept briefly so the map can
    /// cross-fade instead of dropping to blank land.
    private(set) var previousActive: ImageryProviderSpec?
    private(set) var previousCombined: CombinedSpec?
    private(set) var switchedAt: CFTimeInterval = 0
    private var specs: [String: ImageryProviderSpec] = [:]
    private var combined: [String: CombinedSpec] = [:]
    private var cacheDir: URL?
    private var requestedCode = ""

    private var memory: [TileKey: CGImage] = [:]
    private var lru: [TileKey] = []
    private var inflight: Set<TileKey> = []
    /// When each tile landed, for the fade-in.
    private var loadedAt: [TileKey: CFTimeInterval] = [:]
    private var fadeTickerRunning = false
    /// Keys that failed to download this session — don't hammer the server.
    private var failed: Set<TileKey> = []
    private static let memoryLimit = 400
    private static let inflightLimit = 10
    static let fadeDuration: CFTimeInterval = 0.35
    static let crossfadeDuration: CFTimeInterval = 1.2

    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        // OSM's tile policy caps apps at 2 parallel connections; being a
        // good citizen everywhere costs little at 256px tile sizes.
        config.httpMaximumConnectionsPerHost = 2
        config.timeoutIntervalForRequest = 20
        config.requestCachePolicy = .returnCacheDataElseLoad
        return URLSession(configuration: config)
    }()

    /// The active source's display name for the toolbar button.
    var activeLabel: String? {
        activeCombined?.code ?? active?.code
    }

    var hasActiveSource: Bool { active != nil || activeCombined != nil }

    /// Zoom ceiling for the active source (max member ceiling for combined).
    var activeMaxZL: Int {
        if let activeCombined {
            return activeCombined.members.compactMap { specs[$0.code]?.maxZL }.max() ?? 21
        }
        return active?.maxZL ?? 21
    }

    /// Takes the engine's source list: every single source's preview and
    /// every combined source's layers (with their own previews and extent
    /// boxes), and points the disk cache at the data root.
    func configure(sources: [O4ImagerySource], dataRoot: URL?) {
        specs = [:]
        combined = [:]
        for source in sources {
            if let preview = source.preview {
                specs[source.code] = ImageryProviderSpec(code: source.code, preview: preview)
            }
            for member in source.members {
                if let preview = member.preview {
                    specs[member.code] = ImageryProviderSpec(code: member.code, preview: preview)
                }
            }
            if source.combined, !source.members.isEmpty {
                var members: [CombinedSpec.Member] = []
                for member in source.members {
                    var bbox: (minLon: Double, minLat: Double, maxLon: Double, maxLat: Double)?
                    if let b = member.bbox, b.count == 4 {
                        bbox = (minLon: b[0], minLat: b[1], maxLon: b[2], maxLat: b[3])
                    }
                    members.append(CombinedSpec.Member(code: member.code, bbox: bbox))
                }
                combined[source.code] = CombinedSpec(code: source.code, members: members)
            }
        }
        cacheDir = dataRoot?.appendingPathComponent("Previews/livemap", isDirectory: true)
        setProvider(requestedCode)
    }

    /// Realtime provider switch: the map re-requests visible tiles from the
    /// new source on its next draw. Unmappable/unknown codes fall back to
    /// OSM, exactly like the Qt map.
    func setProvider(_ code: String) {
        requestedCode = code
        let nextCombined = combined[code]
        let next = nextCombined == nil ? (specs[code] ?? specs["OSM"]) : nil
        guard next != active || nextCombined != activeCombined else { return }
        // Keep the outgoing source as a cross-fade underlay.
        if active != nil || activeCombined != nil {
            previousActive = active
            previousCombined = activeCombined
            switchedAt = CACurrentMediaTime()
        }
        active = next
        activeCombined = nextCombined
        failed = []
        loadedAt = [:]
        generation += 1
        startFadeTicker()
        imageryLog.notice("live map imagery: \(self.activeLabel ?? "none", privacy: .public)")
    }

    /// True while a source cross-fade is still in progress.
    var crossfading: Bool {
        (previousActive != nil || previousCombined != nil)
            && CACurrentMediaTime() - switchedAt < Self.crossfadeDuration
    }

    /// The single provider that should paint one tile for a given source:
    /// the single spec itself, or — for a combined source — the first
    /// member whose extent contains the tile's center (members are ordered
    /// top-first; a global-extent line is the base).
    private func resolvedSpec(single: ImageryProviderSpec?, combined: CombinedSpec?,
                              z: Int, x: Int, y: Int) -> ImageryProviderSpec? {
        if let single { return single }
        guard let combined else { return nil }
        let lat = WebMercator.lat(tileY: Double(y) + 0.5, z: z)
        let lon = WebMercator.lon(tileX: Double(x) + 0.5, z: z)
        for member in combined.members {
            guard let spec = specs[member.code] else { continue }
            if let bbox = member.bbox {
                guard lon >= bbox.minLon, lon <= bbox.maxLon,
                      lat >= bbox.minLat, lat <= bbox.maxLat else { continue }
            }
            return spec
        }
        return nil
    }

    /// The incoming (or, during a cross-fade, outgoing) source's provider
    /// for one tile.
    private func resolvedSpec(previous: Bool, z: Int, x: Int, y: Int) -> ImageryProviderSpec? {
        previous
            ? resolvedSpec(single: previousActive, combined: previousCombined, z: z, x: x, y: y)
            : resolvedSpec(single: active, combined: activeCombined, z: z, x: x, y: y)
    }

    /// Memory-cached tile with its fade-in alpha, or nil — in which case a
    /// disk-load/download is scheduled and `generation` bumps when the tile
    /// becomes drawable. Cache keys use the RESOLVED member code, so
    /// combined and direct selections share downloads.
    func image(z: Int, x: Int, y: Int) -> (image: CGImage, alpha: CGFloat)? {
        guard let spec = resolvedSpec(single: active, combined: activeCombined,
                                      z: z, x: x, y: y),
              z <= spec.maxZL else { return nil }
        return image(TileKey(code: spec.code, z: z, x: x, y: y), spec: spec)
    }

    /// The map's tile (#1315): past the resolved source's `maxZL` (a
    /// combined member finer or coarser than the others, or the view
    /// overzoomed) it is the deepest available ancestor, with the
    /// sub-square of it to crop and scale up. Never schedules a URL above
    /// `maxZL`.
    func displayImage(z: Int, x: Int, y: Int)
        -> (image: CGImage, alpha: CGFloat, ancestor: MapOverzoom.Ancestor)? {
        guard let spec = resolvedSpec(single: active, combined: activeCombined,
                                      z: z, x: x, y: y) else { return nil }
        let anc = MapOverzoom.ancestor(z: z, x: x, y: y, maxZ: spec.maxZL)
        guard let hit = image(TileKey(code: spec.code, z: anc.z, x: anc.x, y: anc.y),
                              spec: spec) else { return nil }
        return (hit.image, hit.alpha, anc)
    }

    private func image(_ key: TileKey, spec: ImageryProviderSpec)
        -> (image: CGImage, alpha: CGFloat)? {
        if let hit = memory[key] {
            let alpha: CGFloat
            if let start = loadedAt[key] {
                alpha = CGFloat(min(1, (CACurrentMediaTime() - start) / Self.fadeDuration))
            } else {
                alpha = 1
            }
            return (hit, alpha)
        }
        schedule(key, spec: spec)
        return nil
    }

    /// Cache-only peek (never schedules): used for lower-zoom stand-ins
    /// while a tile loads, and for the outgoing source during cross-fades.
    func cachedImage(previous: Bool, z: Int, x: Int, y: Int) -> CGImage? {
        guard let spec = resolvedSpec(previous: previous, z: z, x: x, y: y),
              z <= spec.maxZL else { return nil }
        return memory[TileKey(code: spec.code, z: z, x: x, y: y)]
    }

    /// `cachedImage` past the source's ceiling: the cached ancestor and the
    /// sub-square of it that covers the tile (#1315).
    func cachedDisplayImage(previous: Bool, z: Int, x: Int, y: Int)
        -> (image: CGImage, ancestor: MapOverzoom.Ancestor)? {
        guard let spec = resolvedSpec(previous: previous, z: z, x: x, y: y) else { return nil }
        let anc = MapOverzoom.ancestor(z: z, x: x, y: y, maxZ: spec.maxZL)
        guard let hit = memory[TileKey(code: spec.code, z: anc.z, x: anc.x, y: anc.y)]
        else { return nil }
        return (hit, anc)
    }

    /// Keeps the canvas redrawing while fades/cross-fades are animating.
    private func startFadeTicker() {
        guard !fadeTickerRunning else { return }
        fadeTickerRunning = true
        Task { [weak self] in
            while true {
                try? await Task.sleep(for: .milliseconds(70))
                guard let self else { return }
                let now = CACurrentMediaTime()
                let fading = self.loadedAt.values.contains { now - $0 < Self.fadeDuration }
                let crossing = self.crossfading
                self.generation += 1
                if !fading && !crossing {
                    self.fadeTickerRunning = false
                    if !crossing {
                        self.previousActive = nil
                        self.previousCombined = nil
                    }
                    return
                }
            }
        }
    }

    private func schedule(_ key: TileKey, spec: ImageryProviderSpec) {
        guard !inflight.contains(key), !failed.contains(key),
              inflight.count < Self.inflightLimit else { return }
        inflight.insert(key)
        let cachePath = cacheDir?
            .appendingPathComponent(key.code, isDirectory: true)
            .appendingPathComponent(String(key.z), isDirectory: true)
            .appendingPathComponent("\(key.x)_\(key.y).jpg")
        Task { [weak self] in
            // Disk reads and JPEG decode stay off the main actor.
            var image: CGImage? = await Task.detached(priority: .utility) {
                cachePath.flatMap { Self.decode(contentsOf: $0) }
            }.value
            var fresh: Data?
            if image == nil, let url = spec.url(z: key.z, x: key.x, y: key.y),
               let session = self?.session {
                var request = URLRequest(url: url)
                request.setValue(spec.requestUserAgent, forHTTPHeaderField: "User-Agent")
                // No faked Referer alongside the honest OSM UA.
                if spec.code != "OSM", let referer = spec.referer {
                    request.setValue(referer, forHTTPHeaderField: "Referer")
                }
                if let (data, response) = try? await session.data(for: request),
                   (response as? HTTPURLResponse).map({ $0.statusCode == 200 }) ?? true {
                    image = await Task.detached(priority: .utility) {
                        Self.decode(data: data)
                    }.value
                    if image != nil { fresh = data }
                }
            }
            guard let self else { return }
            self.finish(key, image: image, downloaded: fresh, cachePath: cachePath)
        }
    }

    private func finish(_ key: TileKey, image: CGImage?, downloaded: Data?, cachePath: URL?) {
        inflight.remove(key)
        guard let image else {
            failed.insert(key)
            return
        }
        if let downloaded, let cachePath {
            try? FileManager.default.createDirectory(
                at: cachePath.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? downloaded.write(to: cachePath)
        }
        memory[key] = image
        lru.append(key)
        loadedAt[key] = CACurrentMediaTime()
        if lru.count > Self.memoryLimit {
            for evict in lru.prefix(lru.count - Self.memoryLimit) {
                memory.removeValue(forKey: evict)
                loadedAt.removeValue(forKey: evict)
            }
            lru.removeFirst(lru.count - Self.memoryLimit)
        }
        generation += 1
        startFadeTicker()
    }

    private nonisolated static func decode(contentsOf url: URL) -> CGImage? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return decode(data: data)
    }

    private nonisolated static func decode(data: Data) -> CGImage? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        return CGImageSourceCreateImageAtIndex(source, 0, [
            kCGImageSourceShouldCache: true,
        ] as CFDictionary)
    }
}
