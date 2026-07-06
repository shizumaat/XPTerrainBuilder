import Foundation

/// Finds files in a pack that nothing references — typically leftover ortho
/// source sets (a second run of Ortho4XP against a different imagery source
/// leaves the old textures/*.dds and terrain/*.ter behind, silently doubling
/// the pack on disk).
///
/// Reachability model (deliberately conservative — a false "unused" here
/// would let the user trash working scenery):
/// - Roots: every resource named in the pack's DSF DEFN tables, plus every
///   file exported by library.txt.
/// - `.ter` files can ONLY be referenced by DSFs, so a `.ter` no DSF names is
///   dead — but only when every DSF in the pack parsed successfully.
/// - Images are compared extension-less ("BASE_TEX foo.png" loads foo.dds),
///   `_LIT`/`_NML`/`_NRM` companions live if their base texture lives, and
///   anything that looks like documentation/preview art is excluded.
/// - Images referenced by ANY resource text file other than a dead .ter are
///   alive, even if that file itself is unreachable.
public struct UnusedResourceAnalyzer {
    let installation: Installation

    /// Extensions of files that can be reported unused.
    static let imageExtensions: Set<String> = ["dds", "png", "jpg", "jpeg", "bmp"]
    /// Text resource formats scanned for texture references.
    static let resourceTextExtensions: Set<String> = ["ter", "pol", "obj", "fac", "for", "agp", "str", "lin", "net"]
    /// Path fragments that mark non-scenery imagery (docs, previews).
    static let excludedFragments = ["preview", "screenshot", "thumb", "icon", "logo", "banner",
                                    "/docs/", "/doc/", "/manual/", "/readme"]
    /// Folders whose content is swapped in at runtime (seasonal plugins,
    /// optional variants) — files there are "unreferenced" by design.
    static let protectedFolders: Set<String> = ["options", "optional", "option", "extras", "alternative",
                                                "seasons", "seasonal", "winter", "summer", "spring",
                                                "autumn", "fall", "snow", "backup"]
    /// Seasonal/variant suffixes that plugins substitute by convention.
    static let protectedSuffixes = ["_winter", "_snow", "_spring", "_summer", "_autumn", "_fall", "_wet", "_dry"]
    /// A pack containing any of these is driven by a plugin that loads files
    /// on its own terms — reachability can't be established from scenery
    /// formats, so the whole pack is skipped.
    static let pluginMarkerExtensions: Set<String> = ["xpl", "wt", "lua", "acf"]
    static let pluginMarkerNames: Set<String> = ["xsb_aircraft.txt"]

    public init(installation: Installation) {
        self.installation = installation
    }

    public func analyze(
        progress: ((String) -> Void)? = nil,
        onPack: ((Finding, UnusedResourceGroup?) -> Void)? = nil
    ) -> (findings: [Finding], groups: [UnusedResourceGroup]) {
        let packs = installation.packs.filter { !$0.isLaminar }
        guard !packs.isEmpty else { return ([], []) }

        var partial = [(Finding, UnusedResourceGroup?)?](repeating: nil, count: packs.count)
        let lock = NSLock()
        var completed = 0

        partial.withUnsafeMutableBufferPointer { buffer in
            let buf = UnsafeSendableBuffer(buffer)
            DispatchQueue.concurrentPerform(iterations: packs.count) { i in
                let result = autoreleasepool { scanPack(packs[i]) }
                lock.lock()
                buf.buffer[i] = result
                completed += 1
                let done = completed
                lock.unlock()
                progress?("\(done)/\(packs.count) packs")
                if let result {
                    onPack?(result.0, result.1)
                }
            }
        }

        var findings: [Finding] = []
        var groups: [UnusedResourceGroup] = []
        for case let (finding, group)? in partial {
            findings.append(finding)
            if let group { groups.append(group) }
        }
        groups.sort { $0.totalBytes > $1.totalBytes }
        return (findings, groups)
    }

    // MARK: - Per-pack scan

    func scanPack(_ pack: SceneryPack) -> (Finding, UnusedResourceGroup?)? {
        let fm = FileManager.default
        let packPrefix = pack.url.path + "/"

        var dsfURLs: [URL] = []
        var terFiles: [(url: URL, size: Int64)] = []
        var textFiles: [URL] = []
        var images: [(url: URL, size: Int64)] = []

        guard let enumerator = fm.enumerator(
            at: pack.url,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return nil }

        for case let url as URL in enumerator {
            let ext = url.pathExtension.lowercased()
            if Self.pluginMarkerExtensions.contains(ext)
                || Self.pluginMarkerNames.contains(url.lastPathComponent.lowercased())
                || (url.hasDirectoryPath && url.lastPathComponent.lowercased() == "plugins") {
                return nil // plugin-managed pack: reachability unknowable, skip silently
            }
            if ext == "dsf" {
                dsfURLs.append(url)
            } else if Self.imageExtensions.contains(ext) {
                let size = Int64((try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
                images.append((url, size))
            } else if Self.resourceTextExtensions.contains(ext) {
                textFiles.append(url)
                if ext == "ter" {
                    let size = Int64((try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
                    terFiles.append((url, size))
                }
            }
        }

        // Only DSF-driven packs: without tiles there is no authoritative root
        // set, and libraries/plugin content would be guesswork.
        guard !dsfURLs.isEmpty, !images.isEmpty || !terFiles.isEmpty else { return nil }

        // --- DSF roots ---------------------------------------------------
        var dsfTerrains = Set<String>()
        var unparsableDSFs = 0
        for url in dsfURLs {
            switch DSFReader.readDefinitions(url: url) {
            case .ok(let defs):
                for terrain in defs.terrains {
                    dsfTerrains.insert(Self.normalize(terrain))
                }
            case .compressed, .invalid:
                unparsableDSFs += 1
            }
        }

        // Can't verify anything if a DSF is opaque — bail out loudly rather
        // than guess.
        if unparsableDSFs > 0 {
            return (Finding(
                checkID: "UNUSED-00",
                severity: .info,
                category: .unusedResources,
                title: "'\(pack.name)': could not verify unused files",
                detail: "\(unparsableDSFs) of \(dsfURLs.count) DSF tiles are compressed or unreadable, so resource reachability can't be established for this pack.",
                path: pack.url.path
            ), nil)
        }

        // --- Dead .ter (the stale-ortho-source signature) -----------------
        var deadTer: [(url: URL, size: Int64)] = []
        var deadTerKeys = Set<String>()
        if !dsfURLs.isEmpty {
            for (url, size) in terFiles {
                let key = Self.normalize(String(url.path.dropFirst(packPrefix.count)))
                if !dsfTerrains.contains(key) {
                    deadTer.append((url, size))
                    deadTerKeys.insert(url.path.lowercased())
                }
            }
        }

        // --- Image references from live resource files --------------------
        var referenced = Set<String>() // extension-stripped, normalized keys
        for file in textFiles where !deadTerKeys.contains(file.path.lowercased()) {
            for ref in Self.textureReferences(in: file) {
                // Resolve relative to the referencing file, and also against
                // the pack root — authors are inconsistent, over-inclusion is
                // the safe direction.
                let dir = file.deletingLastPathComponent()
                referenced.insert(Self.strippedKey(dir.appendingPathComponent(ref).path))
                referenced.insert(Self.strippedKey(pack.url.appendingPathComponent(ref).path))
            }
        }
        // library.txt exports are externally reachable.
        if pack.isLibrary {
            let libraryTxt = pack.url.appendingPathComponent("library.txt")
            if let text = TextFile.contents(of: libraryTxt) {
                for line in text.split(separator: "\n") {
                    let parts = line.split(separator: " ", omittingEmptySubsequences: true).map(String.init)
                    guard parts.first?.hasPrefix("EXPORT") == true, parts.count >= 3 else { continue }
                    let realPath = parts.last!
                    referenced.insert(Self.strippedKey(pack.url.appendingPathComponent(realPath).path))
                }
            }
        }

        // --- Orphan images -------------------------------------------------
        var orphanImages: [(url: URL, size: Int64)] = []
        for (url, size) in images {
            let lowerPath = url.path.lowercased()
            if Self.excludedFragments.contains(where: { lowerPath.contains($0) }) { continue }
            // Seasonal/optional content is swapped in by plugins at runtime.
            let folderNames = url.deletingLastPathComponent().pathComponents.map { $0.lowercased() }
            if folderNames.contains(where: { Self.protectedFolders.contains($0) }) { continue }

            let key = Self.strippedKey(url.path)
            if referenced.contains(key) { continue }
            // _LIT/_NML/_NRM companions follow their base texture.
            if let base = Self.companionBase(of: key), referenced.contains(base) { continue }
            // Seasonal variants follow their base texture too.
            if let base = Self.seasonalBase(of: key), referenced.contains(base) { continue }
            orphanImages.append((url, size))
        }

        let orphans = (deadTer + orphanImages).sorted { $0.size > $1.size }
        guard !orphans.isEmpty else { return nil }

        let files = orphans.map { UnusedFile(path: $0.url.path, sizeBytes: $0.size) }
        let group = UnusedResourceGroup(packName: pack.name, packPath: pack.url.path, files: files)
        let sizeText = ByteCountFormatter.string(fromByteCount: group.totalBytes, countStyle: .file)
        let terNote = deadTer.isEmpty ? "" : " \(deadTer.count) of them are .ter terrain definitions no DSF tile references — the signature of a leftover ortho imagery set."

        let finding = Finding(
            checkID: "UNUSED-01",
            severity: group.totalBytes > 100 * 1024 * 1024 ? .warning : .info,
            category: .unusedResources,
            title: "'\(pack.name)': \(files.count) unreferenced file\(files.count == 1 ? "" : "s") (\(sizeText))",
            detail: "No DSF tile, object, polygon, terrain or library export in this pack references these files.\(terNote) They can be moved to the Trash from the Unused Resources view (recoverable, and tracked in Modifications).",
            path: pack.url.path,
            suggestion: "Review the list in the Unused Resources category, then Trash Selected — every file is recoverable from the Trash and listed under Window ▸ Modifications.",
            fixability: .assisted
        )
        return (finding, group)
    }

    // MARK: - Reference extraction

    /// Texture-ish references in a resource text file: any line whose first
    /// token mentions TEX (TEXTURE, BASE_TEX_NOWRAP, TEXTURE_MAP …) — the
    /// last token is the path.
    static func textureReferences(in url: URL) -> [String] {
        // TEXTURE-family directives sit in the header of every X-Plane text
        // format, so 256 KB covers even pathological files — and never pulls
        // the megabytes of geometry that follow in OBJs.
        guard let text = TextFile.head(of: url, maxBytes: 256 * 1024) else { return [] }
        var refs: [String] = []
        for line in text.split(separator: "\n", omittingEmptySubsequences: true) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }
            let parts = trimmed.split(separator: " ", omittingEmptySubsequences: true)
            guard parts.count >= 2, let keyword = parts.first, keyword.uppercased().contains("TEX") else {
                continue
            }
            refs.append(String(parts.last!).replacingOccurrences(of: "\\", with: "/"))
        }
        return refs
    }

    /// Lowercased, "/"-normalized, ".."-resolved path.
    static func normalize(_ path: String) -> String {
        let unified = path.replacingOccurrences(of: "\\", with: "/").lowercased()
        var components: [String] = []
        for component in unified.split(separator: "/") {
            switch component {
            case ".": continue
            case "..": if !components.isEmpty { components.removeLast() }
            default: components.append(String(component))
            }
        }
        return components.joined(separator: "/")
    }

    /// Normalized path without its extension — X-Plane substitutes .dds for
    /// .png transparently, so image identity is extension-blind.
    static func strippedKey(_ path: String) -> String {
        let normalized = normalize(path)
        guard let dot = normalized.lastIndex(of: "."),
              !normalized[normalized.index(after: dot)...].contains("/")
        else { return normalized }
        return String(normalized[..<dot])
    }

    /// "…/runway_lit" -> "…/runway"; nil when the name has no companion suffix.
    static func companionBase(of strippedKey: String) -> String? {
        for suffix in ["_lit", "_nml", "_nrm", "_normal"] where strippedKey.hasSuffix(suffix) {
            return String(strippedKey.dropLast(suffix.count))
        }
        return nil
    }

    /// "…/apron_winter" -> "…/apron"; nil when the name has no seasonal suffix.
    static func seasonalBase(of strippedKey: String) -> String? {
        for suffix in protectedSuffixes where strippedKey.hasSuffix(suffix) {
            return String(strippedKey.dropLast(suffix.count))
        }
        return nil
    }
}

/// Total size on disk of a directory tree, in bytes.
public enum DiskUsage {
    public static func sizeOfDirectory(at url: URL) -> Int64 {
        let fm = FileManager.default
        guard let enumerator = fm.enumerator(
            at: url,
            includingPropertiesForKeys: [.totalFileAllocatedSizeKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
        ) else { return 0 }
        var total: Int64 = 0
        for case let file as URL in enumerator {
            let values = try? file.resourceValues(forKeys: [.totalFileAllocatedSizeKey, .fileSizeKey])
            total += Int64(values?.totalFileAllocatedSize ?? values?.fileSize ?? 0)
        }
        return total
    }
}
