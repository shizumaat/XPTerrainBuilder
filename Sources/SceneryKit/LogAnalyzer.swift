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
        /// Airports X-Plane dropped ATC controllers for ("...has lost some
        /// controllers due to bad frequencies"): (icao, display name).
        public var controllerLosses: [(icao: String, name: String)] = []
        public var linesScanned = 0
    }

    static let controllerLossRegex = try! NSRegularExpression(
        pattern: #"The airport (\S+) \((.*?)\) has lost some controllers due to bad frequencies"#)

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

            // ATC controllers X-Plane dropped over bad frequencies — handled
            // as their own finding (attributed to the owning pack), not as
            // generic noise.
            if let m = controllerLossRegex.firstMatch(in: line, options: [], range: range),
               let icao = line.substring(match: m, group: 1) {
                result.controllerLosses.append((icao, line.substring(match: m, group: 2) ?? icao))
                continue
            }

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

        // ATC controller losses: X-Plane's own verdict is the ground truth
        // (its grouping rules resist clean reverse-engineering — see
        // HANDOVER). For airports a custom pack owns, diagnose the pack's
        // apt.dat and point at a real-world frequency source; losses in
        // Laminar's default data aren't the user's to fix.
        var defaultDataLosses: [(icao: String, name: String)] = []
        var seenLossICAOs = Set<String>()
        for loss in scan.controllerLosses {
            guard seenLossICAOs.insert(loss.icao).inserted else { continue }
            guard let pack = installation.packs.first(where: {
                !$0.isLaminar && $0.isInstalled && $0.airports[loss.icao] != nil
            }) else {
                defaultDataLosses.append(loss)
                continue
            }
            let aptURL = pack.url.appendingPathComponent("Earth nav data/apt.dat")
            let suspects = Self.outOfBandControllers(icao: loss.icao, aptURL: aptURL)
            let evidence = suspects.isEmpty
                ? "Check the airport's ATC frequency rows (1050–1056) in apt.dat."
                : "Controllers with no frequency inside X-Plane's 118.000–136.990 MHz band:\n"
                    + suspects.map { "  \($0.controller): \($0.frequencies)" }.joined(separator: "\n")
            // Military fields tower on UHF (225–400 MHz), which X-Plane's
            // ATC cannot model — the real-world VHF partner frequency is the
            // fix, not deleting the controller.
            let lookupURL = loss.icao.first == "K" || loss.icao.count <= 4 && loss.icao.first == "P"
                ? URL(string: "https://www.airnav.com/airport/\(loss.icao)")
                : URL(string: "https://ourairports.com/airports/\(loss.icao)/frequencies.html")
            findings.append(Finding(
                checkID: "LOG-91",
                severity: .warning,
                category: .packageHealth,
                title: "ATC controllers dropped: \(loss.icao)",
                detail: "X-Plane dropped ATC controllers at \(loss.icao) (\(loss.name)) because they have no frequency in the 118.000–136.990 MHz band — typically military UHF-only entries. \(evidence)",
                path: aptURL.path,
                suggestion: "Apply Fix to add an in-band VHF row to each dropped controller: the published frequency (looked up on AirNav/OurAirports when you apply) when one exists, otherwise an unused in-band channel. UHF rows stay; backed up and revertible.",
                url: lookupURL,
                fixability: .auto,
                proposedFix: .repairControllerFrequencies(aptPath: aptURL.path, icao: loss.icao),
                packName: pack.name,
                packKind: pack.kind
            ))
        }
        if !defaultDataLosses.isEmpty {
            let list = defaultDataLosses.map { "\($0.icao) (\($0.name))" }.joined(separator: ", ")
            findings.append(Finding(
                checkID: "LOG-92",
                severity: .info,
                category: .developerDebug,
                title: "\(defaultDataLosses.count) default-data airports dropped ATC controllers",
                detail: "X-Plane's own Global Airports data has controllers without an in-band (118.000–136.990 MHz) frequency at: \(list). Mostly military fields whose towers are UHF-only. This is Laminar's data — nothing in this install to fix.",
                path: installation.logURL.path,
                suggestion: "Fixable only upstream via the X-Plane Scenery Gateway.",
                fixability: .manual
            ))
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

    /// Named ATC controller groups at `icao` whose every frequency is
    /// outside X-Plane's VHF band — the concrete rows behind an "airport has
    /// lost some controllers" log line. Groups by (row code, raw name):
    /// whitespace differences split groups exactly as X-Plane sees them
    /// (a real Global Airports bug pattern: "Ämari  Tower" vs "Ämari Tower").
    static func outOfBandControllers(
        icao: String, aptURL: URL
    ) -> [(controller: String, frequencies: String)] {
        guard let text = TextFile.contents(of: aptURL) else { return [] }
        var groups: [String: [Int]] = [:]  // "code|raw name" -> kHz
        var order: [String] = []
        var inAirport = false
        for rawLine in TextFile.lines(text) {
            let line = String(rawLine)
            let parts = line.split(whereSeparator: { $0 == " " || $0 == "\t" }).map(String.init)
            guard parts.count >= 2 else { continue }
            switch parts[0] {
            case "1", "16", "17":
                inAirport = parts.count > 4 && parts[4] == icao
            case "1052", "1053", "1054", "1055", "1056", "52", "53", "54", "55", "56":
                guard inAirport, let raw = Int(parts[1]) else { continue }
                let khz = parts[0].count == 2 ? raw * 10 : raw
                // Raw name: everything after the second field, spacing intact.
                let isSpace: (Character) -> Bool = { $0 == " " || $0 == "\t" }
                var rest = Substring(line)
                rest = rest.drop(while: isSpace)
                rest = rest.drop(while: { !isSpace($0) })  // field 1 (row code)
                rest = rest.drop(while: isSpace)
                rest = rest.drop(while: { !isSpace($0) })  // field 2 (frequency)
                let name = rest.drop(while: isSpace)
                let key = "\(parts[0])|\(name)"
                if groups[key] == nil { order.append(key) }
                groups[key, default: []].append(khz)
            default:
                break
            }
        }
        return order.compactMap { key in
            guard let freqs = groups[key],
                  !freqs.contains(where: { (118_000...136_990).contains($0) }) else { return nil }
            let name = key.split(separator: "|", maxSplits: 1).last.map(String.init) ?? key
            let list = freqs.map { String(format: "%.3f MHz", Double($0) / 1000) }
                .joined(separator: ", ")
            return (name.isEmpty ? key : name, list)
        }
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
            let packURL = installation.customSceneryURL.appendingPathComponent(export.packName).resolvingSymlinksInPath()
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
            let packURL = installation.customSceneryURL.appendingPathComponent(packName).resolvingSymlinksInPath()
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
