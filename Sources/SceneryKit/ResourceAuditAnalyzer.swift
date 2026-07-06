import Foundation

/// One pass per pack over the full resource graph, answering both directions:
///
/// **Missing** (RES-01…04): every DSF definition-table entry is resolved
/// against pack files, installed library exports, and X-Plane's default
/// libraries — *before X-Plane ever runs*. Near-misses go through the
/// PathRepair matcher (case / normalization / mojibake) and get auto-rename
/// fixes; texture references from live files are validated too.
///
/// **Unused** (UNUSED-01): breadth-first reachability from the roots (DSF
/// definitions + library.txt exports) through file references. Anything on
/// disk that no root can reach is dead weight — leftover ortho imagery sets,
/// dead objects AND their textures.
///
/// Conservative by construction: DSF-driven packs only, plugin-managed packs
/// skipped, seasonal/options content protected, packs with unreadable DSFs
/// excluded loudly, image matching extension-blind (X-Plane substitutes
/// .dds for .png), ASCII differences never "repaired".
public struct ResourceAuditAnalyzer {
    let installation: Installation

    /// Extensions of files that can be reported unused and traversed.
    /// ags/agb (autogen strings/blocks) matter: simHeaven-style packs chain
    /// DSF → autogen → objects → textures, and dropping the link marks the
    /// whole object tree unused.
    static let imageExtensions: Set<String> = ["dds", "png", "jpg", "jpeg", "bmp"]
    static let resourceTextExtensions: Set<String> = ["ter", "pol", "obj", "fac", "for", "agp", "str", "lin", "net", "ags", "agb"]
    static var traversableExtensions: Set<String> { imageExtensions.union(resourceTextExtensions) }

    /// Path fragments that mark non-scenery imagery (docs, previews).
    static let excludedFragments = ["preview", "screenshot", "thumb", "icon", "logo", "banner",
                                    "/docs/", "/doc/", "/manual/", "/readme"]
    /// Folders whose content is swapped in at runtime (seasonal plugins,
    /// optional variants) — files there are "unreferenced" by design.
    static let protectedFolders: Set<String> = ["options", "optional", "option", "extras", "alternative",
                                                "seasons", "seasonal", "winter", "summer", "spring",
                                                "autumn", "fall", "snow", "backup"]
    static let protectedSuffixes = ["_winter", "_snow", "_spring", "_summer", "_autumn", "_fall", "_wet", "_dry"]
    /// A pack containing any of these is driven by a plugin that loads files
    /// on its own terms — reachability can't be established.
    static let pluginMarkerExtensions: Set<String> = ["xpl", "wt", "lua", "acf"]
    static let pluginMarkerNames: Set<String> = ["xsb_aircraft.txt"]

    static let maxFindingsPerCheckPerPack = 5

    public init(installation: Installation) {
        self.installation = installation
    }

    public func analyze(
        progress: ((String) -> Void)? = nil,
        onPack: (([Finding], UnusedResourceGroup?) -> Void)? = nil
    ) -> (findings: [Finding], groups: [UnusedResourceGroup]) {
        let packs = installation.packs.filter { !$0.isLaminar && $0.isInstalled }
        guard !packs.isEmpty else { return ([], []) }

        var partial = [([Finding], UnusedResourceGroup?)?](repeating: nil, count: packs.count)
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
                if let result, !result.0.isEmpty || result.1 != nil {
                    onPack?(result.0, result.1)
                }
            }
        }

        var findings: [Finding] = []
        var groups: [UnusedResourceGroup] = []
        for case let (packFindings, group)? in partial {
            findings.append(contentsOf: packFindings)
            if let group { groups.append(group) }
        }
        groups.sort { $0.totalBytes > $1.totalBytes }
        return (findings, groups)
    }

    // MARK: - Per-pack audit

    struct FileEntry {
        let url: URL
        let size: Int64
        let modified: Date?
    }

    func scanPack(_ pack: SceneryPack) -> ([Finding], UnusedResourceGroup?)? {
        let fm = FileManager.default
        let packPrefix = pack.url.path + "/"

        var dsfURLs: [URL] = []
        var files: [String: FileEntry] = [:]        // normalized rel path -> entry
        var strippedToRel: [String: String] = [:]   // extension-blind key -> rel path

        guard let enumerator = fm.enumerator(
            at: pack.url,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey, .contentModificationDateKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return nil }

        for case let url as URL in enumerator {
            let ext = url.pathExtension.lowercased()
            if Self.pluginMarkerExtensions.contains(ext)
                || Self.pluginMarkerNames.contains(url.lastPathComponent.lowercased())
                || (url.hasDirectoryPath && url.lastPathComponent.lowercased() == "plugins") {
                return nil // plugin-managed: reachability unknowable
            }
            if ext == "dsf" {
                dsfURLs.append(url)
                continue
            }
            guard Self.traversableExtensions.contains(ext) else { continue }
            let rel = Self.normalize(String(url.path.dropFirst(packPrefix.count)))
            let values = try? url.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey])
            files[rel] = FileEntry(url: url, size: Int64(values?.fileSize ?? 0),
                                   modified: values?.contentModificationDate)
            strippedToRel[Self.strippedKey(rel)] = rel
        }

        // Only DSF-driven packs: without tiles there is no authoritative root set.
        guard !dsfURLs.isEmpty, !files.isEmpty else { return nil }

        // --- DSF definition tables --------------------------------------
        var defnEntries: [String: Int] = [:] // original entry -> tile count
        var unparsableDSFs = 0
        for url in dsfURLs {
            switch DSFReader.readDefinitions(url: url) {
            case .ok(let defs):
                for entry in defs.allResources {
                    defnEntries[entry, default: 0] += 1
                }
            case .compressed, .invalid:
                unparsableDSFs += 1
            }
        }

        if unparsableDSFs > 0 {
            return ([Finding(
                checkID: "UNUSED-00",
                severity: .info,
                category: .unusedResources,
                title: "'\(pack.name)': could not audit resources",
                detail: "\(unparsableDSFs) of \(dsfURLs.count) DSF tiles are compressed or unreadable, so resource reachability can't be established for this pack.",
                path: pack.url.path,
                packName: pack.name,
                packKind: pack.kind
            )], nil)
        }

        // --- Resolve every definition entry; collect roots + missing ----
        var findings: [Finding] = []
        var roots: [String] = []
        var renameCount = 0, missingCount = 0, nearMissCount = 0
        var deprecatedRefs: [(entry: String, export: LibraryExport)] = []

        for (entry, tileCount) in defnEntries.sorted(by: { $0.key < $1.key }) {
            // Built-in resources (terrain_Water etc.) have no path separator.
            guard entry.contains("/") || entry.lowercased().hasSuffix(".ter")
                    || entry.lowercased().hasSuffix(".obj") else { continue }
            let normalized = Self.normalize(entry)

            if files[normalized] != nil {
                roots.append(normalized)
                continue
            }
            if installation.libraryIndex.caseInsensitiveMatch(for: entry) != nil {
                if let dep = installation.libraryIndex.fullyDeprecatedMatch(for: entry) {
                    deprecatedRefs.append((entry, dep))
                }
                continue
            }
            if installation.defaultLibraryIndex.caseInsensitiveMatch(for: entry) != nil {
                if let dep = installation.defaultLibraryIndex.fullyDeprecatedMatch(for: entry) {
                    deprecatedRefs.append((entry, dep))
                }
                continue
            }

            // Pack-local near-miss: case/normalization/mojibake damage.
            if let resolution = PathRepair.resolve(relativePath: entry, under: pack.url) {
                if resolution.isExact {
                    roots.append(normalized) // normalization edge; file is there
                    continue
                }
                if resolution.mismatches.count == 1, let mismatch = resolution.mismatches.first {
                    renameCount += 1
                    if true { // every missing resource is listed — no cap
                        let expectedURL = mismatch.actual.deletingLastPathComponent()
                            .appendingPathComponent(mismatch.expectedName)
                        findings.append(Finding(
                            checkID: "RES-02",
                            severity: .error,
                            category: .missingResource,
                            title: "Damaged file name: \(mismatch.actual.lastPathComponent)",
                            detail: "\(tileCount) DSF tile\(tileCount == 1 ? "" : "s") in '\(pack.name)' reference '\(entry)'. The file is on disk but spelled '\(mismatch.actual.lastPathComponent)' — non-ASCII characters mangled by an archive tool, so X-Plane can't match it.",
                            path: mismatch.actual.path,
                            suggestion: "Apply Fix to rename it to exactly '\(mismatch.expectedName)'. Recorded in Modifications, revertible.",
                            fixability: .auto,
                            proposedFix: .renameFile(fromPath: mismatch.actual.path, toPath: expectedURL.path),
                            packName: pack.name,
                            packKind: pack.kind
                        ))
                    }
                    // The damaged file is reachable once renamed; treat as root
                    // so its own references stay alive.
                    let damagedRel = Self.normalize(String(resolution.url.path.dropFirst(packPrefix.count)))
                    roots.append(damagedRel)
                    continue
                }
            }

            // Installed library with a near-miss export (typo / version drift)?
            // Only worth computing when that library prefix is installed —
            // edit-distance over the whole index for every local miss is
            // what turned the full-install audit into minutes.
            let near = installation.libraryIndex.packsExportingPrefix(of: entry).isEmpty
                ? [] : installation.libraryIndex.nearestExports(to: entry, limit: 1)
            if let best = near.first {
                nearMissCount += 1
                if true {
                    findings.append(Finding(
                        checkID: "RES-03",
                        severity: .warning,
                        category: .missingResource,
                        title: "No exact library match: \(lastComponent(entry))",
                        detail: "'\(entry)' (referenced by \(tileCount) tile\(tileCount == 1 ? "" : "s") in '\(pack.name)') isn't exported by any installed or default library, but '\(best.virtualPath)' in '\(best.packName)' is very close — likely a typo or a library version mismatch.",
                        suggestion: "Update '\(best.packName)', or the scenery needs an older library version.",
                        fixability: .assisted,
                        packName: pack.name,
                        packKind: pack.kind
                    ))
                }
                continue
            }

            // Genuinely unresolvable.
            missingCount += 1
            if true {
                let prefix = entry.split(separator: "/").first.map(String.init) ?? entry
                let known = KnownLibraries.lookup(prefix: prefix)
                findings.append(Finding(
                    checkID: "RES-01",
                    severity: .error,
                    category: .missingResource,
                    title: "Missing resource: \(lastComponent(entry))",
                    detail: "\(tileCount) DSF tile\(tileCount == 1 ? "" : "s") in '\(pack.name)' reference '\(entry)', which is neither in the pack nor exported by any installed or default library. X-Plane will fail to draw it (or refuse to load the airport).",
                    path: pack.url.path,
                    suggestion: known.map { "Install \($0.name)." }
                        ?? "Search x-plane.org downloads for '\(prefix)' — the library it belongs to is probably not installed.",
                    url: known?.url ?? KnownLibraries.searchURL(for: prefix),
                    fixability: .assisted,
                    packName: pack.name,
                    packKind: pack.kind
                ))
            }
            _ = tileCount
        }

        // Deprecated library references still draw today, so they're an
        // author heads-up, not a user problem: one summary finding per pack.
        if !deprecatedRefs.isEmpty {
            let paths = deprecatedRefs.map { $0.entry }.sorted()
            let shown = paths.prefix(10).joined(separator: "\n")
            let more = paths.count > 10 ? "\n…and \(paths.count - 10) more" : ""
            let libs = Set(deprecatedRefs.map { $0.export.packName }).sorted().joined(separator: ", ")
            findings.append(Finding(
                checkID: "RES-05",
                severity: .info,
                category: .developerDebug,
                title: "References \(paths.count) deprecated library asset\(paths.count == 1 ? "" : "s")",
                detail: "'\(pack.name)' references virtual paths that \(libs) marks DEPRECATED or SEMI_DEPRECATED. X-Plane still resolves them (some to blank placeholder art), but Laminar may remove them in a future version:\n\(shown)\(more)",
                path: pack.url.path,
                suggestion: "Scenery authors should migrate to the current library paths. Nothing for users to do.",
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        // Library exports are externally reachable roots. Parse through
        // LibraryIndex — the hand-rolled space-split that used to live here
        // silently dropped tab-separated files (simHeaven ships tab+CRLF)
        // and flagged entire export sets as unused. Alternate configs
        // ("library - orthos.txt") count as roots too: users activate them
        // by renaming, and deletion must survive that.
        let rootItems = (try? fm.contentsOfDirectory(at: pack.url, includingPropertiesForKeys: nil)) ?? []
        for item in rootItems
        where item.lastPathComponent.lowercased().hasPrefix("library")
            && item.pathExtension.lowercased() == "txt" {
            var exportIndex = LibraryIndex()
            exportIndex.indexLibraryFile(at: item, packName: pack.name)
            for exports in exportIndex.exports.values {
                for export in exports {
                    let rel = Self.normalize(export.realPath)
                    if files[rel] != nil {
                        roots.append(rel)
                    } else if Self.imageExtensions.contains((rel as NSString).pathExtension),
                              let actual = strippedToRel[Self.strippedKey(rel)] {
                        roots.append(actual) // exports resolve extension-blind too
                    }
                }
            }
        }

        // --- Reachability BFS -------------------------------------------
        var aliveExact = Set<String>()
        var aliveStripped = Set<String>()
        var queue = roots
        var missingTextures: [(from: String, ref: String)] = []
        var missingTextureCount = 0

        while let rel = queue.popLast() {
            guard !aliveExact.contains(rel), let entry = files[rel] else { continue }
            aliveExact.insert(rel)
            aliveStripped.insert(Self.strippedKey(rel))

            let ext = (rel as NSString).pathExtension
            guard Self.resourceTextExtensions.contains(ext) else { continue }

            let dir = (rel as NSString).deletingLastPathComponent
            for ref in Self.fileReferences(in: entry.url) {
                // X-Plane resolves texture refs relative to the referencing
                // file, then pack-relative, then falls back to the file's own
                // directory by bare name (authors rely on this).
                let bareName = (ref as NSString).lastPathComponent
                let candidates = [
                    Self.normalize(dir.isEmpty ? ref : dir + "/" + ref),
                    Self.normalize(ref),
                    Self.normalize(dir.isEmpty ? bareName : dir + "/" + bareName),
                ]
                var resolved = false
                for candidate in candidates {
                    if files[candidate] != nil {
                        queue.append(candidate)
                        resolved = true
                        break
                    }
                    // Images resolve extension-blind (foo.png loads foo.dds).
                    if Self.imageExtensions.contains((candidate as NSString).pathExtension),
                       let actual = strippedToRel[Self.strippedKey(candidate)] {
                        queue.append(actual)
                        resolved = true
                        break
                    }
                }
                // Deep ../ escapes point outside the pack — can't audit those.
                if !resolved, !ref.hasPrefix("../.."),
                   Self.imageExtensions.contains((ref as NSString).pathExtension.lowercased()) {
                    missingTextureCount += 1
                    missingTextures.append((from: rel, ref: ref))
                }
            }
        }

        for miss in missingTextures {
            // Missing _LIT/_NML companions only cost night lighting / normal
            // detail — cosmetic, not structural.
            let stripped = Self.strippedKey(miss.ref)
            let cosmetic = Self.companionBase(of: stripped) != nil
            findings.append(Finding(
                checkID: "RES-04",
                severity: cosmetic ? .info : .warning,
                category: .missingResource,
                title: "Missing texture: \(lastComponent(miss.ref))",
                detail: "'\(miss.from)' in '\(pack.name)' references '\(miss.ref)', which doesn't exist in the pack (checked extension-blind, including X-Plane's same-folder fallback).\(cosmetic ? " It's a _LIT/_NML companion, so only night lighting or normal-map detail is lost." : " X-Plane draws the surface untextured or fails to load the object.")",
                path: pack.url.appendingPathComponent(miss.from).path,
                suggestion: "The pack is missing files — re-download/reinstall it, or report to the author.",
                fixability: .assisted,
                packName: pack.name,
                packKind: pack.kind
            ))
        }
        // --- Unused: everything unreachable ------------------------------
        var orphans: [(rel: String, entry: FileEntry)] = []
        for (rel, entry) in files {
            if aliveExact.contains(rel) { continue }
            let lower = rel.lowercased()
            if Self.excludedFragments.contains(where: { ("/" + lower).contains($0) }) { continue }
            let folderNames = (rel as NSString).deletingLastPathComponent
                .split(separator: "/").map { $0.lowercased() }
            if folderNames.contains(where: { Self.protectedFolders.contains(String($0)) }) { continue }

            let stripped = Self.strippedKey(rel)
            if Self.imageExtensions.contains((rel as NSString).pathExtension) {
                if aliveStripped.contains(stripped) { continue }
                if let base = Self.companionBase(of: stripped), aliveStripped.contains(base) { continue }
                if let base = Self.seasonalBase(of: stripped), aliveStripped.contains(base) { continue }
            }
            orphans.append((rel, entry))
        }

        guard !orphans.isEmpty || !findings.isEmpty else { return nil }

        // Orphans here are CANDIDATES: nothing inside this pack reaches them.
        // They only become findings after verifyUnused clears them against
        // every other pack's escaping references.
        var group: UnusedResourceGroup? = nil
        if !orphans.isEmpty {
            let sorted = orphans.sorted { $0.entry.size > $1.entry.size }
            let unusedFiles = sorted.map {
                UnusedFile(path: $0.entry.url.path, sizeBytes: $0.entry.size, modifiedDate: $0.entry.modified)
            }
            group = UnusedResourceGroup(packName: pack.name, packPath: pack.url.path, files: unusedFiles)
        }

        return (findings, group)
    }

    /// The per-group finding, built only for groups that survived verification.
    public static func unusedFinding(for group: UnusedResourceGroup, packKind: PackKind?) -> Finding {
        let sizeText = ByteCountFormatter.string(fromByteCount: group.totalBytes, countStyle: .file)
        let count = group.files.count
        return Finding(
            checkID: "UNUSED-01",
            severity: group.totalBytes > 100 * 1024 * 1024 ? .warning : .info,
            category: .unusedResources,
            title: "'\(group.packName)': \(count) unreachable file\(count == 1 ? "" : "s") (\(sizeText))",
            detail: "No DSF tile, library export or cross-package reference in the entire installation can reach these files, directly or through any chain of references — leftover imagery sets, dead objects and their textures.",
            path: group.packPath,
            suggestion: "Review in the Unused Resources view, then Trash Selected — recoverable from the Trash, tracked in Modifications.",
            fixability: .assisted,
            packName: group.packName,
            packKind: packKind
        )
    }

    /// Deletion-grade verification: sweep EVERY pack in the install (all of
    /// Custom Scenery plus the disabled folder, regardless of analysis scope)
    /// for `../`-style references that escape their own pack, and drop any
    /// candidate such a reference lands on. Cross-pack references are rare —
    /// in-pack reachability plus library exports cover the normal cases — but
    /// "unused" is a promise the Trash button relies on.
    ///
    /// Known limits, both conservative in the keep direction: escapes are
    /// resolved lexically (a `..` crossing a symlinked pack boundary resolves
    /// differently on disk), and refs from uninstalled packs are resolved at
    /// their current (disabled-folder) location.
    public static func verifyUnused(
        candidates: [UnusedResourceGroup],
        allPacks: [SceneryPack],
        progress: ((Int, Int) -> Void)? = nil
    ) -> [UnusedResourceGroup] {
        guard !candidates.isEmpty else { return [] }
        var refs: [String] = []
        let lock = NSLock()
        var done = 0
        DispatchQueue.concurrentPerform(iterations: allPacks.count) { i in
            let found = collectEscapeRefs(in: allPacks[i])
            lock.lock()
            refs.append(contentsOf: found)
            done += 1
            let d = done
            lock.unlock()
            if d % 25 == 0 || d == allPacks.count { progress?(d, allPacks.count) }
        }
        return verifyUnused(candidates: candidates, externalRefs: refs)
    }

    /// ONE canonical spelling for every path that takes part in cross-pack
    /// matching. Foundation is treacherous here: standardizedFileURL adds
    /// /private when collapsing "..", while resolvingSymlinksInPath strips it
    /// only when the full path EXISTS — so two spellings of the same file
    /// need not compare equal. Resolve symlinks (60% of the reference
    /// install's packs are symlinked), then normalize the /private prefix by
    /// hand.
    static func canonicalPath(_ url: URL) -> String {
        var path = url.standardizedFileURL.resolvingSymlinksInPath().path
        for prefix in ["/private/var/", "/private/tmp/", "/private/etc/"]
        where path.hasPrefix(prefix) {
            path = String(path.dropFirst("/private".count))
        }
        return path.lowercased()
    }

    /// Canonical absolute paths this pack references OUTSIDE its own folder
    /// (../-style escapes in text resources and library configs). Cacheable
    /// per pack: the expensive half of unused-file verification.
    public static func collectEscapeRefs(in pack: SceneryPack) -> [String] {
        var found = Set<String>()
        autoreleasepool {
            let packPrefix = canonicalPath(pack.url) + "/"
            guard let enumerator = FileManager.default.enumerator(
                at: pack.url,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles, .skipsPackageDescendants]
            ) else { return }
            for case let url as URL in enumerator {
                let ext = url.pathExtension.lowercased()
                let isLibraryConfig = ext == "txt"
                    && url.lastPathComponent.lowercased().hasPrefix("library")
                guard resourceTextExtensions.contains(ext) || isLibraryConfig else { continue }
                for ref in fileReferences(in: url) where ref.contains("../") {
                    // X-Plane resolves relative to the referencing file,
                    // with a pack-root fallback.
                    for base in [url.deletingLastPathComponent(), pack.url] {
                        let abs = canonicalPath(base.appendingPathComponent(ref))
                        guard !abs.hasPrefix(packPrefix) else { continue }
                        found.insert(abs)
                    }
                }
            }
        }
        return Array(found)
    }

    /// Matching half of the verification: candidates survive only if no
    /// collected external reference (or reference chain from one) lands on
    /// them.
    public static func verifyUnused(
        candidates: [UnusedResourceGroup],
        externalRefs: [String]
    ) -> [UnusedResourceGroup] {
        guard !candidates.isEmpty else { return [] }
        let canonical = { (url: URL) in canonicalPath(url) }

        var refExact = Set<String>()     // canonical paths referenced from outside their pack
        var refStripped = Set<String>()  // ditto, images without extension
        for ref in externalRefs {
            refExact.insert(ref)
            if imageExtensions.contains((ref as NSString).pathExtension) {
                refStripped.insert((ref as NSString).deletingPathExtension)
            }
        }

        // A referenced base image keeps its _LIT/_NML and seasonal companions.
        func matches(_ lower: String, exact: Set<String>, stripped strippedSet: Set<String>) -> Bool {
            if exact.contains(lower) { return true }
            let ns = lower as NSString
            guard imageExtensions.contains(ns.pathExtension) else { return false }
            let stripped = ns.deletingPathExtension
            if strippedSet.contains(stripped) { return true }
            if let base = companionBase(of: stripped), strippedSet.contains(base) { return true }
            if let base = seasonalBase(of: stripped), strippedSet.contains(base) { return true }
            return false
        }

        // An externally-referenced candidate keeps its own reference CHAIN:
        // if some pack reaches an orphaned .ter, that .ter's texture must
        // survive too, or trashing it breaks the external reference.
        var candPackRoot: [String: String] = [:]     // canonical -> pack path
        var candOriginal: [String: String] = [:]     // canonical -> path as recorded
        var candStripped: [String: [String]] = [:]   // image stripped key -> members
        for group in candidates {
            for file in group.files {
                let key = canonical(URL(fileURLWithPath: file.path))
                candPackRoot[key] = group.packPath
                candOriginal[key] = file.path
                if imageExtensions.contains((key as NSString).pathExtension) {
                    candStripped[(key as NSString).deletingPathExtension, default: []].append(key)
                }
            }
        }

        var keptExact = Set<String>()
        var keptStrippedImages = Set<String>()
        var queue = candOriginal.keys.filter { matches($0, exact: refExact, stripped: refStripped) }
        while let lower = queue.popLast() {
            guard !keptExact.contains(lower) else { continue }
            keptExact.insert(lower)
            let ns = lower as NSString
            if imageExtensions.contains(ns.pathExtension) {
                keptStrippedImages.insert(ns.deletingPathExtension)
            }
            guard resourceTextExtensions.contains(ns.pathExtension),
                  let original = candOriginal[lower], let packRoot = candPackRoot[lower]
            else { continue }
            let fileURL = URL(fileURLWithPath: original)
            for ref in fileReferences(in: fileURL) {
                for base in [fileURL.deletingLastPathComponent(), URL(fileURLWithPath: packRoot)] {
                    let abs = canonical(base.appendingPathComponent(ref))
                    if candOriginal[abs] != nil {
                        queue.append(abs)
                    } else if let members = candStripped[(abs as NSString).deletingPathExtension] {
                        queue.append(contentsOf: members) // extension-blind image
                    }
                }
            }
        }

        return candidates.compactMap { group in
            var group = group
            group.files.removeAll {
                matches(canonical(URL(fileURLWithPath: $0.path)),
                        exact: keptExact, stripped: keptStrippedImages)
            }
            return group.files.isEmpty ? nil : group
        }
    }

    // MARK: - Reference extraction

    /// Every whitespace-separated token that looks like a resource-file path,
    /// on any line — keyword-independent, so facade ROOF lines, autogen
    /// OBJECT lines etc. all count. Directives live in file headers, so a
    /// bounded head-read suffices.
    static func fileReferences(in url: URL) -> [String] {
        guard let text = TextFile.head(of: url, maxBytes: 256 * 1024) else { return [] }
        var refs: [String] = []
        for line in TextFile.lines(text) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }
            for token in trimmed.split(whereSeparator: { $0 == " " || $0 == "\t" }) {
                guard token.contains(".") else { continue }
                let cleaned = token.replacingOccurrences(of: "\\", with: "/")
                let ext = (cleaned as NSString).pathExtension.lowercased()
                if traversableExtensions.contains(ext) {
                    refs.append(cleaned)
                }
            }
            // Directive values can contain spaces ("TEXTURE my tex.png") —
            // token splitting alone shreds those. Also try everything after
            // the directive as one path; a bogus extra ref only errs toward
            // keeping files.
            let value = trimmed.drop(while: { $0 != " " && $0 != "\t" })
                .trimmingCharacters(in: .whitespaces)
            if value.contains(" ") {
                let cleaned = value.replacingOccurrences(of: "\\", with: "/")
                if traversableExtensions.contains((cleaned as NSString).pathExtension.lowercased()) {
                    refs.append(cleaned)
                }
            }
        }
        return refs
    }

    func lastComponent(_ path: String) -> String {
        (path as NSString).lastPathComponent
    }

    // MARK: - Path helpers

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

    /// Normalized path without its extension — image identity is
    /// extension-blind (X-Plane substitutes .dds for .png transparently).
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
