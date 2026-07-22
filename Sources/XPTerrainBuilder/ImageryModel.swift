import Foundation
import SwiftUI
import CoreGraphics
import ImageIO
import QuartzCore
import SceneryKit
import os

private let imageryLog = Logger(subsystem: "com.novemberlima.XPTerrainBuilder", category: "imagery")

/// One imagery source the map can display live: a webmercator provider
/// parsed from an Ortho4XP .lay file. This is the same subset the engine's
/// Qt map supports (grid_type=webmercator → the engine forces request_type
/// "tms" with a url_template); everything else falls back to OSM.
struct ImageryProviderSpec: Equatable {
    let code: String
    let urlTemplate: String
    let maxZL: Int
    let referer: String?
    /// Providers flagged in_GUI=False are internal layers — usable as
    /// combined-provider members but hidden from pickers.
    let inGUI: Bool

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

    /// Parses a Providers/<Region>/<CODE>.lay; nil when the provider isn't
    /// a plain webmercator source the map can hit directly.
    static func parse(layFile: URL) -> ImageryProviderSpec? {
        guard let text = try? String(contentsOf: layFile, encoding: .utf8) else { return nil }
        var fields: [String: String] = [:]
        for line in text.components(separatedBy: .newlines) {
            let parts = line.split(separator: "=", maxSplits: 1)
            guard parts.count == 2 else { continue }
            fields[String(parts[0]).trimmingCharacters(in: .whitespaces)] =
                String(parts[1]).trimmingCharacters(in: .whitespaces)
        }
        guard fields["grid_type"] == "webmercator",
              let template = fields["url_template"], !template.isEmpty
        else { return nil }
        // fake_headers is a python dict literal; lift just the Referer.
        var referer: String?
        if let headers = fields["fake_headers"],
           let range = headers.range(of: "'Referer': '") {
            referer = String(headers[range.upperBound...].prefix(while: { $0 != "'" }))
        }
        return ImageryProviderSpec(
            code: layFile.deletingPathExtension().lastPathComponent,
            urlTemplate: template,
            // Absent max_zl means the source declares NO ceiling (the
            // engine will build it at any ZL) — preview up to the fetch
            // cap. Only 4 of the shipped providers declare a cap.
            maxZL: Int(fields["max_zl"] ?? "") ?? 21,
            referer: referer,
            inGUI: fields["in_GUI"]?.lowercased() != "false")
    }

    /// Engine-compatible URL construction (O4_Imagery_Utils.get_wmts_image,
    /// TMS branch): {zoom} {x} {y} {-y} {quadkey} {switch:a,b,c}.
    func url(z: Int, x: Int, y: Int) -> URL? {
        var s = urlTemplate
            .replacingOccurrences(of: "{zoom}", with: String(z))
            .replacingOccurrences(of: "{x}", with: String(x))
            .replacingOccurrences(of: "{y}", with: String(y))
            .replacingOccurrences(of: "{-y}", with: String((1 << z) - 1 - y))
        if s.contains("{quadkey}") {
            s = s.replacingOccurrences(of: "{quadkey}", with: Self.quadkey(x: x, y: y, z: z))
        }
        if let start = s.range(of: "{switch:"),
           let end = s.range(of: "}", range: start.upperBound..<s.endIndex) {
            let options = s[start.upperBound..<end.lowerBound].split(separator: ",")
            if !options.isEmpty {
                let pick = options[abs(x &+ y) % options.count]
                    .trimmingCharacters(in: .whitespaces)
                s.replaceSubrange(start.lowerBound..<end.upperBound, with: pick)
            }
        }
        return URL(string: s)
    }

    /// Google tile coords → Bing quadkey (O4_Geo_Utils.gtile_to_quadkey).
    static func quadkey(x: Int, y: Int, z: Int) -> String {
        var quadkey = ""
        var tx = x, ty = y
        for step in 1...max(z, 1) {
            let size = 1 << (z - step)
            let a = tx / size, b = ty / size
            tx -= a * size
            ty -= b * size
            quadkey += String(a + 2 * b)
        }
        return quadkey
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

    /// Codes the toolbar picker offers: previewable single providers
    /// (in_GUI ones, like the engine's own dropdown) plus combined
    /// providers that have at least one previewable member, plus OSM.
    var availableProviders: [String] {
        var codes = specs.values.filter { $0.inGUI && $0.code != "SEA" }.map(\.code)
        codes += combined.values
            .filter { $0.members.contains { specs[$0.code] != nil } }
            .map(\.code)
        return Array(Set(codes)).sorted { $0.lowercased() < $1.lowercased() }
    }

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

    /// Scans every .lay and .comb under the engine's Providers folder,
    /// resolves combined members' extents to bboxes (Extents/**.ext
    /// mask_bounds), and points the disk cache at the data root.
    func configure(providersDir: URL?, extentsDir: URL?, dataRoot: URL?) {
        specs = [:]
        combined = [:]
        var combFiles: [URL] = []
        if let providersDir,
           let walker = FileManager.default.enumerator(at: providersDir,
                                                       includingPropertiesForKeys: nil) {
            for case let url as URL in walker {
                if url.pathExtension == "lay",
                   let spec = ImageryProviderSpec.parse(layFile: url) {
                    specs[spec.code] = spec
                } else if url.pathExtension == "comb" {
                    combFiles.append(url)
                }
            }
        }
        // Extent name → bbox, from every .ext's mask_bounds line.
        var extentBounds: [String: (Double, Double, Double, Double)] = [:]
        if let extentsDir,
           let walker = FileManager.default.enumerator(at: extentsDir,
                                                       includingPropertiesForKeys: nil) {
            for case let url as URL in walker where url.pathExtension == "ext" {
                guard let text = try? String(contentsOf: url, encoding: .utf8) else { continue }
                for line in text.components(separatedBy: .newlines)
                where line.hasPrefix("mask_bounds=") {
                    let parts = line.dropFirst("mask_bounds=".count)
                        .split(separator: ",").compactMap { Double($0) }
                    if parts.count == 4 {
                        extentBounds[url.deletingPathExtension().lastPathComponent] =
                            (parts[0], parts[1], parts[2], parts[3])
                    }
                    break
                }
            }
        }
        for url in combFiles {
            guard let text = try? String(contentsOf: url, encoding: .utf8) else { continue }
            var members: [CombinedSpec.Member] = []
            for line in text.components(separatedBy: .newlines) {
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }
                let fields = trimmed.split(separator: " ", omittingEmptySubsequences: true)
                guard fields.count >= 2 else { continue }
                let extent = String(fields[1])
                let bbox = (extent == "global" || extent == "none")
                    ? nil : extentBounds[extent].map {
                        (minLon: $0.0, minLat: $0.1, maxLon: $0.2, maxLat: $0.3)
                    }
                members.append(CombinedSpec.Member(code: String(fields[0]), bbox: bbox))
            }
            let code = url.deletingPathExtension().lastPathComponent
            if !members.isEmpty {
                combined[code] = CombinedSpec(code: code, members: members)
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

    /// Memory-cached tile with its fade-in alpha, or nil — in which case a
    /// disk-load/download is scheduled and `generation` bumps when the tile
    /// becomes drawable. Cache keys use the RESOLVED member code, so
    /// combined and direct selections share downloads.
    func image(z: Int, x: Int, y: Int) -> (image: CGImage, alpha: CGFloat)? {
        guard let spec = resolvedSpec(single: active, combined: activeCombined,
                                      z: z, x: x, y: y),
              z <= spec.maxZL else { return nil }
        let key = TileKey(code: spec.code, z: z, x: x, y: y)
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
        let spec = previous
            ? resolvedSpec(single: previousActive, combined: previousCombined, z: z, x: x, y: y)
            : resolvedSpec(single: active, combined: activeCombined, z: z, x: x, y: y)
        guard let spec, z <= spec.maxZL else { return nil }
        return memory[TileKey(code: spec.code, z: z, x: x, y: y)]
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

/// Web-mercator tile math for the imagery layer.
enum WebMercator {
    static let maxLat = 85.05112878

    /// Fractional tile y for a latitude at zoom z.
    static func tileY(lat: Double, z: Int) -> Double {
        let clamped = min(max(lat, -maxLat), maxLat)
        let rad = clamped * .pi / 180
        return (1 - asinh(tan(rad)) / .pi) / 2 * Double(1 << z)
    }

    /// Latitude of a (fractional) tile-row boundary at zoom z.
    static func lat(tileY y: Double, z: Int) -> Double {
        let n = .pi * (1 - 2 * y / Double(1 << z))
        return atan(sinh(n)) * 180 / .pi
    }

    static func tileX(lon: Double, z: Int) -> Double {
        (lon + 180) / 360 * Double(1 << z)
    }

    static func lon(tileX x: Double, z: Int) -> Double {
        x / Double(1 << z) * 360 - 180
    }
}
