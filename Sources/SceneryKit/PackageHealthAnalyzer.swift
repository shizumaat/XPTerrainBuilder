import Foundation

/// Tunable thresholds. Defaults follow the xpsan spec's guidance; not
/// user-configurable in the prototype.
public struct HealthConfig: Sendable {
    public var heavyObjVertexCount = 10_000     // C-02: heavy OBJ with no LOD
    public var tinyObjFileBytes = 4 * 1024      // C-05: below this an OBJ is at most a couple dozen verts
    public var tinyObjWarnFraction = 0.5        // C-05: warn if >50% of a pack's OBJs are tiny
    public var maxObjTextureDim = 4096          // C-04: object textures above this are suspect
    public var largePNGBytes = 20 * 1024 * 1024 // C-04: PNG this big will stutter at load
    public var maxObjParsesPerPack = 150        // parse only the N largest OBJs per pack
    public var maxFindingsPerCheckPerPack = 5   // keep the report readable
    public var maxObjSpanMeters = 1000.0        // C-12: Laminar: ideal objects are <= 1 km per side
    public var spillLightsPerObjWarn = 50       // C-10: spill lights are deferred-shading fill cost

    /// The machine's practical VRAM budget; performance warnings are judged
    /// against this, not a hard-coded number.
    public var vramBudgetBytes: Int64 = 8 * 1024 * 1024 * 1024

    /// Warn when one non-library pack's textures alone estimate to more than
    /// half the budget.
    public var packVRAMWarnBytes: Int64 { vramBudgetBytes / 2 }
    /// Warn when packs sharing a tile together exceed 3/4 of the budget.
    public var tileVRAMWarnBytes: Int64 { vramBudgetBytes * 3 / 4 }

    public init() {}

    public static func forSystem(_ system: SystemInfo) -> HealthConfig {
        var config = HealthConfig()
        config.vramBudgetBytes = system.vramBudgetBytes
        return config
    }
}

/// Per-pack scan implementing a pragmatic subset of the xpsan check catalog:
/// C-02/C-08 (no LOD), C-03 (instancing-hostile ATTR), C-04 (texture format
/// and sizing), C-05 (tiny objects), plus an overall performance estimate.
///
/// Real installs can hold thousands of packs and hundreds of thousands of
/// files (a 2 TB Custom Scenery is not unusual), so packs are scanned in
/// parallel and only the largest OBJs per pack are fully parsed — small
/// files physically cannot exceed the heavy-object thresholds, and the
/// tiny-object check needs only file sizes.
public struct PackageHealthAnalyzer {
    let installation: Installation
    let config: HealthConfig

    public init(installation: Installation, config: HealthConfig = HealthConfig()) {
        self.installation = installation
        self.config = config
    }

    public struct PackScanResult: Sendable {
        public var findings: [Finding] = []
        public var objFilesParsed = 0
        public var texturesInspected = 0
        /// Estimated texture VRAM of the scanned pack (bytes).
        public var vramEstimateBytes: Int64 = 0
    }

    public struct AggregateResult: Sendable {
        public var findings: [Finding] = []
        public var objFilesParsed = 0
        public var texturesInspected = 0
        /// Pack name -> estimated texture VRAM bytes (non-library packs only).
        public var packVRAM: [String: Int64] = [:]
    }

    /// `progress` and `onPackFindings` are called from worker threads as each
    /// pack completes; both must be thread-safe.
    public func analyze(
        progress: ((String) -> Void)? = nil,
        onPackFindings: (([Finding]) -> Void)? = nil
    ) -> AggregateResult {
        let packs = installation.packs.filter { !$0.isLaminar && $0.isInstalled }
        guard !packs.isEmpty else { return AggregateResult() }

        var partial = [PackScanResult?](repeating: nil, count: packs.count)
        let lock = NSLock()
        var completed = 0

        partial.withUnsafeMutableBufferPointer { buffer in
            let buf = UnsafeSendableBuffer(buffer)
            DispatchQueue.concurrentPerform(iterations: packs.count) { i in
                // autoreleasepool: enumerators and mapped file data would
                // otherwise accumulate open file descriptors across packs.
                let result = autoreleasepool { scanPack(packs[i]) }
                lock.lock()
                buf.buffer[i] = result
                completed += 1
                let done = completed
                lock.unlock()
                progress?("\(packs[i].name) (\(done)/\(packs.count))")
                if !result.findings.isEmpty {
                    onPackFindings?(result.findings)
                }
            }
        }

        var merged = AggregateResult()
        for (pack, result) in zip(packs, partial) {
            guard let result else { continue }
            merged.findings.append(contentsOf: result.findings)
            merged.objFilesParsed += result.objFilesParsed
            merged.texturesInspected += result.texturesInspected
            if !pack.isLibrary {
                merged.packVRAM[pack.name] = result.vramEstimateBytes
            }
        }
        return merged
    }

    public func scanPack(_ pack: SceneryPack) -> PackScanResult {
        var result = PackScanResult()
        let fm = FileManager.default

        var objFiles: [(url: URL, size: Int)] = []
        var textureURLs: [URL] = []
        if let enumerator = fm.enumerator(
            at: pack.url,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) {
            for case let url as URL in enumerator {
                switch url.pathExtension.lowercased() {
                case "obj":
                    let size = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
                    objFiles.append((url, size))
                case "png", "dds":
                    textureURLs.append(url)
                default: break
                }
            }
        }

        // --- OBJ checks -------------------------------------------------
        // File size bounds vertex count (a VT line is ~50-70 bytes), so only
        // the largest files can hold heavy geometry. Parse those; judge the
        // rest by size alone.
        let tinyCount = objFiles.filter { $0.size > 0 && $0.size < config.tinyObjFileBytes }.count
        let toParse = objFiles.sorted { $0.size > $1.size }.prefix(config.maxObjParsesPerPack)

        var noLODHeavy: [(URL, ObjInfo)] = []
        var attrPromotable: [URL] = []
        var blendPingPong: [(URL, Int)] = []
        var heavyAnimated: [(URL, ObjInfo)] = []
        var spillHeavy: [(URL, Int)] = []
        var overspanned: [(URL, Double)] = []
        var packSpillTotal = 0

        for (url, _) in toParse {
            guard let info = ObjParser.parse(url: url) else { continue }
            result.objFilesParsed += 1

            if !info.hasLOD && info.vertexCount >= config.heavyObjVertexCount {
                noLODHeavy.append((url, info))
            }
            // ATTR_no_blend used per-mesh with no blending flips and no GLOBAL
            // equivalent: whole-object state that forfeits hardware instancing.
            if info.perMeshNoBlend > 0 && info.blendStateChanges == 0
                && !info.hasGlobalNoBlend && !info.animated {
                attrPromotable.append(url)
            }
            if info.blendStateChanges >= 3 {
                blendPingPong.append((url, info.blendStateChanges))
            }
            // C-09: animation and dataref-driven state force the object off
            // X-Plane's instanced path (Laminar: "Making 3-d Modeling Less Weird").
            if (info.animated || info.hasLightLevel),
               info.vertexCount >= config.heavyObjVertexCount / 2 {
                heavyAnimated.append((url, info))
            }
            // C-10: spill lights are deferred-shading fill cost.
            packSpillTotal += info.spillLightCount
            if info.spillLightCount >= config.spillLightsPerObjWarn {
                spillHeavy.append((url, info.spillLightCount))
            }
            // C-12: Laminar's ideal object is <= 1 km per side; giant objects
            // defeat frustum culling ("whole object draws for a sliver").
            if let span = info.largestDimension, span > config.maxObjSpanMeters,
               info.vertexCount >= 24 {
                overspanned.append((url, span))
            }
        }

        for (url, info) in noLODHeavy.sorted(by: { $0.1.vertexCount > $1.1.vertexCount }).prefix(config.maxFindingsPerCheckPerPack) {
            let verts = info.vertexCount
            let distance = LODAdvisor.farCullDistance(forLargestDimension: info.largestDimension)
            let sizeClause = info.dimensionsDescription
                .map { "It measures ~\($0), so beyond ~\(distance) m it occupies only a few pixels yet still draws at full detail." }
                ?? "Beyond ~\(distance) m it occupies only a few pixels yet still draws at full detail."
            result.findings.append(Finding(
                checkID: "C-02",
                severity: verts >= config.heavyObjVertexCount * 4 ? .error : .warning,
                category: .packageHealth,
                title: "Heavy object with no LOD: \(url.lastPathComponent)",
                detail: "\(url.lastPathComponent) in '\(pack.name)' has \(verts) vertices and no ATTR_LOD. \(sizeClause)",
                path: url.path,
                suggestion: "Apply Fix to insert 'ATTR_LOD 0 \(distance)' (sized to the object's dimensions) so it stops drawing at distance. The original file is backed up first. A real lower-poly LOD from the author is still better.",
                fixability: .auto,
                proposedFix: .addFarLOD(objPath: url.path, distanceMeters: distance),
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, info) in heavyAnimated.prefix(config.maxFindingsPerCheckPerPack) {
            let reason = info.animated ? "animation (ANIM_*)" : "dataref-driven ATTR_light_level"
            result.findings.append(Finding(
                checkID: "C-09",
                severity: .info,
                category: .packageHealth,
                title: "Animation blocks instancing: \(url.lastPathComponent)",
                detail: "\(url.lastPathComponent) (\(info.vertexCount) vertices) uses \(reason), which takes it off X-Plane's fast instanced drawing path. Cheap for a one-off (windsock, radar); expensive if this object is placed many times.",
                path: url.path,
                suggestion: "If the animation isn't essential, the author can split the animated part into a small separate object so the heavy geometry stays instanced.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, count) in spillHeavy.sorted(by: { $0.1 > $1.1 }).prefix(config.maxFindingsPerCheckPerPack) {
            // Info, not warning: a real cost, but there is no one-click fix
            // yet, and warning-severity should mean "actionable".
            result.findings.append(Finding(
                checkID: "C-10",
                severity: .info,
                category: .packageHealth,
                title: "\(count) spill lights in one object: \(url.lastPathComponent)",
                detail: "Spill lights cost GPU fill in X-Plane's deferred renderer, scaling with the screen area they cover — a dense apron of them is a classic night-FPS killer (Laminar: 'Customizing Spill Lights').",
                path: url.path,
                suggestion: "Reduce the count or radius of spill lights, or use the cheaper parameterized lights for repeated fixtures.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, span) in overspanned.sorted(by: { $0.1 > $1.1 }).prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-12",
                severity: span > config.maxObjSpanMeters * 2.5 ? .warning : .info,
                category: .packageHealth,
                title: "Object spans \(Int(span)) m: \(url.lastPathComponent)",
                detail: "Laminar's guidance is ≤1,000 m per side (500 m is ideal). When any sliver of a huge object is on screen, the whole thing draws — culling and LOD can't help.",
                path: url.path,
                suggestion: "The author should split it into region-sized objects. Not mechanically fixable.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for url in attrPromotable.prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-03",
                severity: .info,
                category: .packageHealth,
                title: "Instancing-hostile ATTR state: \(url.lastPathComponent)",
                detail: "Uses per-mesh ATTR_no_blend uniformly. Promoting it to GLOBAL_no_blend keeps the object on X-Plane's fast instanced drawing path.",
                path: url.path,
                suggestion: "Apply Fix to replace ATTR_no_blend with GLOBAL_no_blend (validated text edit, backed up, revertible).",
                fixability: .auto,
                proposedFix: .promoteGlobalNoBlend(objPath: url.path),
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, flips) in blendPingPong.prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-03",
                severity: .warning,
                category: .packageHealth,
                title: "Blend state ping-pong: \(url.lastPathComponent)",
                detail: "Alternates between ATTR_blend and ATTR_no_blend \(flips) times. Each flip forces extra draw calls and disables instancing.",
                path: url.path,
                suggestion: "The author should reorder geometry so each blend state appears once. Not safe to auto-fix.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        if objFiles.count >= 20,
           Double(tinyCount) / Double(objFiles.count) > config.tinyObjWarnFraction {
            result.findings.append(Finding(
                checkID: "C-05",
                severity: .info,
                category: .packageHealth,
                title: "Many tiny objects in '\(pack.name)'",
                detail: "\(tinyCount) of \(objFiles.count) OBJ files are under \(config.tinyObjFileBytes / 1024) KB (a couple dozen vertices at most). Per-object draw overhead dominates for objects this small.",
                path: pack.url.path,
                suggestion: "Candidates for merging into shared, texture-sharing objects (needs the author's 3-D tooling).",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        // --- Texture checks ---------------------------------------------
        var packVRAM = 0
        var bigPNGs: [(URL, TextureInfo)] = []
        var nonPOT: [(URL, TextureInfo)] = []
        var noMips: [(URL, TextureInfo)] = []
        var oversized: [(URL, TextureInfo)] = []
        var pngCount = 0

        for url in textureURLs {
            guard let info = TextureInspector.inspect(url: url), info.format != .other else { continue }
            result.texturesInspected += 1
            packVRAM += info.estimatedVRAMBytes

            if info.format == .png {
                pngCount += 1
                if info.fileSizeBytes >= config.largePNGBytes {
                    bigPNGs.append((url, info))
                }
            }
            if info.format == .dds && info.mipMapCount <= 1 {
                noMips.append((url, info))
            }
            if !info.isPowerOfTwo && info.width > 0 {
                nonPOT.append((url, info))
            }
            if max(info.width, info.height) > config.maxObjTextureDim {
                oversized.append((url, info))
            }
        }

        for (url, info) in bigPNGs.sorted(by: { $0.1.fileSizeBytes > $1.1.fileSizeBytes }).prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-04",
                severity: .warning,
                category: .packageHealth,
                title: "Large PNG texture: \(url.lastPathComponent)",
                detail: "\(url.lastPathComponent) (\(info.width)x\(info.height), \(ByteCountFormatter.string(fromByteCount: Int64(info.fileSizeBytes), countStyle: .file))) in '\(pack.name)'. PNGs are decompressed and mipmapped on the CPU at load time — a common cause of loading stutter.",
                path: url.path,
                suggestion: "Apply Fix to convert it to a mipmapped, block-compressed DDS (the PNG is kept as a backup and the change is revertible). X-Plane loads the .dds automatically wherever the .png is referenced.",
                fixability: .auto,
                proposedFix: .convertPNGToDDS(pngPath: url.path),
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, info) in noMips.prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-04",
                severity: .warning,
                category: .packageHealth,
                title: "DDS without mipmaps: \(url.lastPathComponent)",
                detail: "\(url.lastPathComponent) (\(info.width)x\(info.height)) has no mipmap chain, causing shimmering and worse texture-cache behavior.",
                path: url.path,
                suggestion: "Regenerate the DDS with mipmaps enabled.",
                fixability: .assisted,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, info) in nonPOT.prefix(config.maxFindingsPerCheckPerPack) {
            let isPNG = info.format == .png
            result.findings.append(Finding(
                checkID: "C-04",
                severity: .info,
                category: .packageHealth,
                title: "Non-power-of-two texture: \(url.lastPathComponent)",
                detail: "\(info.width)x\(info.height) — X-Plane handles it, but it wastes memory and prevents some optimizations.",
                path: url.path,
                suggestion: isPNG
                    ? "Apply Fix to resample it to the nearest power of two and convert to mipmapped DDS (UVs are normalized, so nothing shifts). Backed up, revertible."
                    : "Re-export at a power-of-two size in the author's pipeline.",
                fixability: isPNG ? .auto : .manual,
                proposedFix: isPNG ? .convertPNGToDDS(pngPath: url.path) : nil,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for (url, info) in oversized.sorted(by: { max($0.1.width, $0.1.height) > max($1.1.width, $1.1.height) }).prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-04",
                severity: .info,
                category: .packageHealth,
                title: "Very large texture: \(url.lastPathComponent)",
                detail: "\(info.width)x\(info.height) (\(info.format.rawValue.uppercased())) — above \(config.maxObjTextureDim)px. Fine for orthos, wasteful for object textures.",
                path: url.path,
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        // --- Performance summary -----------------------------------------
        result.vramEstimateBytes = Int64(packVRAM)
        let vramStr = ByteCountFormatter.string(fromByteCount: Int64(packVRAM), countStyle: .memory)
        let budgetStr = ByteCountFormatter.string(fromByteCount: config.vramBudgetBytes, countStyle: .memory)

        if pack.isLibrary {
            // A library's textures load only when other scenery places its
            // assets — its total size is not a per-frame cost.
            if Int64(packVRAM) >= config.vramBudgetBytes {
                result.findings.append(Finding(
                    checkID: "PERF-03",
                    severity: .info,
                    category: .performance,
                    title: "Large library: '\(pack.name)' (~\(vramStr) of textures)",
                    detail: "Libraries load only the assets other scenery actually places, so this is not all resident at once. It matters only when many packs draw from it in the same region.",
                    path: pack.url.path,
                    packName: pack.name,
                    packKind: pack.kind
                ))
            }
        } else if Int64(packVRAM) >= config.packVRAMWarnBytes {
            result.findings.append(Finding(
                checkID: "PERF-01",
                severity: .warning,
                category: .performance,
                title: "'\(pack.name)' is likely performance-intensive",
                detail: "Estimated texture VRAM footprint is ~\(vramStr) across \(result.texturesInspected) textures\(pngCount > 0 ? " (\(pngCount) PNG)" : "") — more than half of this Mac's ~\(budgetStr) usable VRAM on its own. Exceeding VRAM causes a sudden FPS cliff and paging stutter.",
                path: pack.url.path,
                suggestion: "Convert large PNGs to DDS (Apply Fix on the C-04 findings), lower X-Plane's texture quality when flying here, or look for a 'lite' version.",
                fixability: .assisted,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        if packSpillTotal >= 500 {
            result.findings.append(Finding(
                checkID: "C-10",
                severity: .info,
                category: .performance,
                title: "'\(pack.name)' has ~\(packSpillTotal) spill lights",
                detail: "Sampled across the pack's largest objects. Spill lights cost deferred-shading fill scaled by covered screen area — the classic 'FPS tanks at night at this airport' signature.",
                path: pack.url.path,
                suggestion: "If night FPS suffers here, look for a 'lite lights' option from the author, or lower X-Plane's rendering settings at night.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        return result
    }
}

/// Wrapper to move an UnsafeMutableBufferPointer across concurrentPerform's
/// Sendable boundary. Safe here because each iteration writes a distinct index.
struct UnsafeSendableBuffer<T>: @unchecked Sendable {
    let buffer: UnsafeMutableBufferPointer<T>
    init(_ buffer: UnsafeMutableBufferPointer<T>) { self.buffer = buffer }
}
