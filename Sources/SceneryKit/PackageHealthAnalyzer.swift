import Foundation

/// Tunable thresholds. Defaults follow the xpsan spec's guidance; not
/// user-configurable in the prototype.
public struct HealthConfig: Sendable {
    public var heavyObjVertexCount = 10_000     // C-02: heavy OBJ with no LOD
    public var tinyObjFileBytes = 4 * 1024      // C-05: below this an OBJ is at most a couple dozen verts
    public var tinyObjWarnFraction = 0.5        // C-05: warn if >50% of a pack's OBJs are tiny
    public var maxObjTextureDim = 4096          // C-04: object textures above this are suspect
    public var largePNGBytes = 20 * 1024 * 1024 // C-04: PNG this big will stutter at load
    public var packVRAMWarnBytes = 2 * 1024 * 1024 * 1024 // performance summary threshold
    public var maxObjParsesPerPack = 150        // parse only the N largest OBJs per pack
    public var maxFindingsPerCheckPerPack = 5   // keep the report readable

    public init() {}
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
    }

    /// `progress` and `onPackFindings` are called from worker threads as each
    /// pack completes; both must be thread-safe.
    public func analyze(
        progress: ((String) -> Void)? = nil,
        onPackFindings: (([Finding]) -> Void)? = nil
    ) -> PackScanResult {
        let packs = installation.packs.filter { !$0.isLaminar }
        guard !packs.isEmpty else { return PackScanResult() }

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

        var merged = PackScanResult()
        for case let result? in partial {
            merged.findings.append(contentsOf: result.findings)
            merged.objFilesParsed += result.objFilesParsed
            merged.texturesInspected += result.texturesInspected
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

        var noLODHeavy: [(URL, Int)] = []
        var attrPromotable: [URL] = []
        var blendPingPong: [(URL, Int)] = []

        for (url, _) in toParse {
            guard let info = ObjParser.parse(url: url) else { continue }
            result.objFilesParsed += 1

            if !info.hasLOD && info.vertexCount >= config.heavyObjVertexCount {
                noLODHeavy.append((url, info.vertexCount))
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
        }

        for (url, verts) in noLODHeavy.sorted(by: { $0.1 > $1.1 }).prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-02",
                severity: verts >= config.heavyObjVertexCount * 4 ? .error : .warning,
                category: .packageHealth,
                title: "Heavy object with no LOD: \(url.lastPathComponent)",
                detail: "\(url.lastPathComponent) in '\(pack.name)' has \(verts) vertices and no ATTR_LOD. Every placement draws at full detail regardless of distance.",
                path: url.path,
                suggestion: "Ask the author for LODs, or add a far-cull LOD (a one-line text edit: 'ATTR_LOD 0 <distance>') so it stops drawing at distance.",
                fixability: .assisted
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
                suggestion: "Replace ATTR_no_blend with GLOBAL_no_blend in the OBJ header (text edit).",
                fixability: .auto
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
                fixability: .manual
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
                fixability: .manual
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
                suggestion: "Convert to DDS (pre-compressed, pre-mipmapped) with XGrinder or the author's pipeline.",
                fixability: .assisted
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
                fixability: .assisted
            ))
        }

        for (url, info) in nonPOT.prefix(config.maxFindingsPerCheckPerPack) {
            result.findings.append(Finding(
                checkID: "C-04",
                severity: .info,
                category: .packageHealth,
                title: "Non-power-of-two texture: \(url.lastPathComponent)",
                detail: "\(info.width)x\(info.height) — X-Plane handles it, but it wastes memory and prevents some optimizations.",
                path: url.path,
                fixability: .manual
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
                fixability: .manual
            ))
        }

        // --- Performance summary -----------------------------------------
        if packVRAM >= config.packVRAMWarnBytes {
            let vramStr = ByteCountFormatter.string(fromByteCount: Int64(packVRAM), countStyle: .memory)
            result.findings.append(Finding(
                checkID: "PERF-01",
                severity: .warning,
                category: .performance,
                title: "'\(pack.name)' is likely performance-intensive",
                detail: "Estimated texture VRAM footprint is ~\(vramStr) across \(result.texturesInspected) textures\(pngCount > 0 ? " (\(pngCount) PNG)" : ""). Exceeding available VRAM causes a sudden FPS cliff and paging stutter.",
                path: pack.url.path,
                suggestion: "Lower X-Plane's texture quality when using this pack, convert large PNGs to DDS, or look for a 'lite' version of the package.",
                fixability: .assisted
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
