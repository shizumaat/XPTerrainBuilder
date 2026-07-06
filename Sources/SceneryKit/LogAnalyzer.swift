import Foundation

/// A missing-resource event extracted from Log.txt.
public struct MissingResource: Sendable, Hashable {
    public let virtualPath: String
    /// The scenery pack that referenced it, if the log said.
    public let referencedFrom: String?
}

/// Scans X-Plane's Log.txt for scenery-related errors and, for each missing
/// resource, works out *why* it is missing:
///   1. Library installed + near-identical export exists  -> case/typo mismatch.
///   2. Library installed but no similar export           -> outdated/partial library.
///   3. Library not installed                             -> link to download it.
public struct LogAnalyzer {
    let installation: Installation

    public init(installation: Installation) {
        self.installation = installation
    }

    // MARK: - Log parsing

    static let missingResourcePatterns: [NSRegularExpression] = {
        let patterns = [
            // XP: Failed to find resource 'vpath', referenced from scenery package 'Custom Scenery/Foo/'.
            #"Failed to find resource '([^']+)'(?:, referenced from (?:scenery package|file) '([^']+)')?"#,
            // XP: Failed to find resource vpath, referenced from ... (unquoted variant)
            #"Failed to find resource ([^,']+), referenced from (?:scenery package|file) ([^\s']+)"#,
            // Library system: Could not locate object/resource: vpath
            #"Could not locate (?:object|resource):? '?([^'\n]+?)'?\s*$"#,
        ]
        return patterns.compactMap {
            try? NSRegularExpression(pattern: $0, options: [.caseInsensitive])
        }
    }()

    public struct LogScanResult: Sendable {
        public var missing: [MissingResource] = []
        public var otherSceneryErrors: [String] = []
        public var linesScanned = 0
    }

    public static func parseLog(text: String) -> LogScanResult {
        var result = LogScanResult()
        var seen = Set<MissingResource>()

        for rawLine in TextFile.lines(text) {
            result.linesScanned += 1
            let line = String(rawLine)
            let range = NSRange(line.startIndex..., in: line)

            var matched = false
            for regex in missingResourcePatterns {
                guard let m = regex.firstMatch(in: line, options: [], range: range) else { continue }
                let vpath = line.substring(match: m, group: 1)?
                    .trimmingCharacters(in: CharacterSet(charactersIn: " .'"))
                guard let vpath, !vpath.isEmpty else { continue }
                var pack = line.substring(match: m, group: 2)
                pack = pack?.replacingOccurrences(of: "Custom Scenery/", with: "")
                    .trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
                let missing = MissingResource(virtualPath: vpath, referencedFrom: pack)
                if seen.insert(missing).inserted {
                    result.missing.append(missing)
                }
                matched = true
                break
            }
            if matched { continue }

            // Generic scenery subsystem errors worth surfacing (capped later).
            if line.contains("E/SCN") || line.contains("E/DSF") || line.contains("E/APT") {
                result.otherSceneryErrors.append(line.trimmingCharacters(in: .whitespaces))
            }
        }
        return result
    }

    // MARK: - Findings

    public func analyze() -> (findings: [Finding], linesScanned: Int) {
        analyze(logRead: TextFile.read(installation.logURL))
    }

    /// The log is read *before* the installation scan opens thousands of
    /// directories (see Analyzer.run) — under a GUI app's 256-fd soft limit,
    /// reading it afterwards can fail with "too many open files".
    public func analyze(logRead: TextFile.ReadResult) -> (findings: [Finding], linesScanned: Int) {
        let text: String
        switch logRead {
        case .ok(let contents):
            text = contents
        case .notFound:
            return ([Finding(
                checkID: "LOG-00",
                severity: .info,
                category: .installation,
                title: "Log.txt not found",
                detail: "No Log.txt at \(installation.logURL.path). Run X-Plane once so a log exists, then re-analyze.",
                path: installation.logURL.path
            )], 0)
        case .unreadable(let reason):
            return ([Finding(
                checkID: "LOG-00",
                severity: .warning,
                category: .installation,
                title: "Log.txt exists but could not be read",
                detail: "Reading \(installation.logURL.path) failed: \(reason). This is usually a permissions problem — check System Settings › Privacy & Security if macOS is restricting the app's file access.",
                path: installation.logURL.path
            )], 0)
        case .tooLarge(let size):
            return ([Finding(
                checkID: "LOG-00",
                severity: .warning,
                category: .installation,
                title: "Log.txt is unusually large",
                detail: "Log.txt is \(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file)) — too large to scan. A plugin may be spamming the log. Delete it and run X-Plane once to get a fresh log.",
                path: installation.logURL.path
            )], 0)
        }

        let scan = Self.parseLog(text: text)
        var findings: [Finding] = []

        for missing in scan.missing {
            findings.append(diagnose(missing).attributed(packName: missing.referencedFrom))
        }

        // Cap the generic error list so a noisy log doesn't drown the report.
        let generics = scan.otherSceneryErrors.prefix(25)
        if !generics.isEmpty {
            findings.append(Finding(
                checkID: "LOG-90",
                severity: .info,
                category: .missingResource,
                title: "\(scan.otherSceneryErrors.count) other scenery-related log message\(scan.otherSceneryErrors.count == 1 ? "" : "s")",
                detail: generics.joined(separator: "\n"),
                path: installation.logURL.path
            ))
        }
        return (findings, scan.linesScanned)
    }

    func diagnose(_ missing: MissingResource) -> Finding {
        let vpath = missing.virtualPath
        let fromPack = missing.referencedFrom.map { " (referenced by \($0))" } ?? ""
        let index = installation.libraryIndex

        // 1. Same path exists in a library, differing only by case.
        if let export = index.caseInsensitiveMatch(for: vpath), export.virtualPath != vpath {
            return Finding(
                checkID: "LOG-01",
                severity: .error,
                category: .missingResource,
                title: "Case mismatch: \(lastComponent(vpath))",
                detail: "The scenery asks for '\(vpath)'\(fromPack), but the library '\(export.packName)' exports it as '\(export.virtualPath)'. The names differ only in letter case, which breaks on some setups and library versions.",
                path: installation.customSceneryURL.appendingPathComponent(export.packName).path,
                suggestion: "Fix the reference in the referencing package (or report it to its author): use the exact path '\(export.virtualPath)'.",
                fixability: .assisted
            )
        }

        // 1b. Exact export exists but the sim still complained — real file may be absent on disk.
        if let export = index.caseInsensitiveMatch(for: vpath) {
            let packURL = installation.customSceneryURL.appendingPathComponent(export.packName)
            let fileURL = packURL.appendingPathComponent(export.realPath)
            if resolveCaseInsensitive(fileURL) == nil {
                return Finding(
                    checkID: "LOG-02",
                    severity: .error,
                    category: .missingResource,
                    title: "Broken library export: \(lastComponent(vpath))",
                    detail: "'\(export.packName)' promises '\(vpath)' via its library.txt, but the backing file '\(export.realPath)' is not on disk. The library install is likely incomplete or corrupted.",
                    path: packURL.path,
                    suggestion: "Re-download and reinstall '\(export.packName)'.",
                    fixability: .assisted
                )
            }
            return Finding(
                checkID: "LOG-03",
                severity: .warning,
                category: .missingResource,
                title: "Resource missing at load time: \(lastComponent(vpath))",
                detail: "'\(vpath)'\(fromPack) is exported by '\(export.packName)' and the file exists now, but X-Plane could not find it when the log was written. The library may have been installed or renamed after that session, or load order hides it.",
                path: packURL.path,
                suggestion: "Re-run X-Plane and re-analyze; if it persists, check scenery_packs.ini ordering.",
                fixability: .assisted
            )
        }

        // Pack-relative resources: X-Plane resolves paths like
        // 'Some Folder/model.obj' against the referencing pack before the
        // library system. If the file is there under a case/normalization/
        // mojibake-damaged name, the precise fix is a rename.
        if let packName = missing.referencedFrom {
            let packURL = installation.customSceneryURL.appendingPathComponent(packName)
            if FileManager.default.fileExists(atPath: packURL.path),
               let resolution = PathRepair.resolve(relativePath: vpath, under: packURL) {
                if resolution.isExact {
                    return Finding(
                        checkID: "LOG-03",
                        severity: .warning,
                        category: .missingResource,
                        title: "Resource missing at load time: \(lastComponent(vpath))",
                        detail: "'\(vpath)'\(fromPack) exists in the pack now, but X-Plane could not find it when the log was written. It may have been installed or fixed after that session.",
                        path: resolution.url.path,
                        suggestion: "Re-run X-Plane and re-analyze.",
                        fixability: .assisted
                    )
                }
                if resolution.mismatches.count == 1, let mismatch = resolution.mismatches.first {
                    let actualName = mismatch.actual.lastPathComponent
                    let expectedURL = mismatch.actual.deletingLastPathComponent()
                        .appendingPathComponent(mismatch.expectedName)
                    return Finding(
                        checkID: "LOG-08",
                        severity: .error,
                        category: .missingResource,
                        title: "Damaged file name: \(actualName)",
                        detail: "The scenery asks for '\(vpath)'\(fromPack). The file is on disk, but its name is spelled '\(actualName)' instead of '\(mismatch.expectedName)' — non-ASCII characters mangled by an archive tool or encoding mix-up, so X-Plane can't match it.",
                        path: mismatch.actual.path,
                        suggestion: "Apply Fix to rename it to exactly '\(mismatch.expectedName)'. The rename is recorded in Modifications and can be reverted.",
                        fixability: .auto,
                        proposedFix: .renameFile(fromPath: mismatch.actual.path, toPath: expectedURL.path)
                    )
                }
                // Several components damaged — explain rather than chain renames.
                let list = resolution.mismatches
                    .map { "'\($0.actual.lastPathComponent)' → '\($0.expectedName)'" }
                    .joined(separator: ", ")
                return Finding(
                    checkID: "LOG-08",
                    severity: .error,
                    category: .missingResource,
                    title: "Damaged path: \(lastComponent(vpath))",
                    detail: "'\(vpath)'\(fromPack) exists on disk but several path components have encoding-damaged names: \(list).",
                    path: resolution.url.path,
                    suggestion: "Rename the listed folders/files to the exact referenced spellings (innermost last).",
                    fixability: .assisted
                )
            }
        }

        let owningPacks = index.packsExportingPrefix(of: vpath)
        let prefix = vpath.split(separator: "/").first.map(String.init) ?? vpath

        // 2. Library is installed — look for a near-miss (typo) export.
        if !owningPacks.isEmpty {
            let near = index.nearestExports(to: vpath, limit: 3)
            if let best = near.first {
                let alternatives = near.map { "'\($0.virtualPath)'" }.joined(separator: ", ")
                return Finding(
                    checkID: "LOG-04",
                    severity: .error,
                    category: .missingResource,
                    title: "Probable typo in path: \(lastComponent(vpath))",
                    detail: "'\(vpath)'\(fromPack) is not exported by installed library '\(best.packName)', but very similar paths are: \(alternatives). This is usually a typo in the referencing scenery or a renamed asset in a newer library version.",
                    path: installation.customSceneryURL.appendingPathComponent(best.packName).path,
                    suggestion: "The closest installed asset is '\(best.virtualPath)'. Fix the reference, or update/downgrade '\(best.packName)' to a version that still ships the old path.",
                    fixability: .assisted
                )
            }
            return Finding(
                checkID: "LOG-05",
                severity: .warning,
                category: .missingResource,
                title: "Library installed but asset absent: \(lastComponent(vpath))",
                detail: "A library for '\(prefix)/…' is installed (\(owningPacks.sorted().joined(separator: ", "))) but it does not export '\(vpath)'\(fromPack). Your library version is probably older or newer than what the scenery expects.",
                suggestion: "Update \(owningPacks.sorted().first ?? "the library") to the latest version; if already current, the scenery needs an older version or an update itself.",
                url: KnownLibraries.lookup(prefix: prefix)?.url ?? KnownLibraries.searchURL(for: prefix),
                fixability: .assisted
            )
        }

        // 3. Library not installed at all.
        if let known = KnownLibraries.lookup(prefix: prefix) {
            return Finding(
                checkID: "LOG-06",
                severity: .error,
                category: .missingResource,
                title: "Missing library: \(known.name)",
                detail: "'\(vpath)'\(fromPack) belongs to \(known.name), which is not installed in Custom Scenery.",
                suggestion: "Download and install \(known.name), then restart X-Plane.",
                url: known.url,
                fixability: .assisted
            )
        }
        return Finding(
            checkID: "LOG-07",
            severity: .error,
            category: .missingResource,
            title: "Missing library: \(prefix)",
            detail: "'\(vpath)'\(fromPack) refers to a library prefix '\(prefix)' that no installed pack exports. The library is most likely not installed.",
            suggestion: "Search x-plane.org downloads for '\(prefix)' and install the library it belongs to.",
            url: KnownLibraries.searchURL(for: prefix),
            fixability: .assisted
        )
    }

    // MARK: - Helpers

    func lastComponent(_ path: String) -> String {
        (path as NSString).lastPathComponent
    }

    /// Finds a file even if the on-disk name differs in case from the given URL.
    /// Returns the actual URL if found (macOS is usually case-insensitive, but
    /// scenery must also work on case-sensitive volumes, so we check exactly).
    func resolveCaseInsensitive(_ url: URL) -> URL? {
        let fm = FileManager.default
        if fm.fileExists(atPath: url.path) { return url }
        // Walk down from the parent comparing case-insensitively.
        let parent = url.deletingLastPathComponent()
        guard let entries = try? fm.contentsOfDirectory(atPath: parent.path) else { return nil }
        let target = url.lastPathComponent.lowercased()
        for entry in entries where entry.lowercased() == target {
            return parent.appendingPathComponent(entry)
        }
        return nil
    }
}

extension String {
    /// Substring for a capture group of an NSRegularExpression match, or nil.
    func substring(match: NSTextCheckingResult, group: Int) -> String? {
        guard group < match.numberOfRanges else { return nil }
        let nsRange = match.range(at: group)
        guard nsRange.location != NSNotFound, let range = Range(nsRange, in: self) else { return nil }
        return String(self[range])
    }
}
