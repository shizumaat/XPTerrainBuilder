import Foundation

/// Detects redundant or conflicting scenery packs:
///  - two or more custom packs covering the same airport (wasted space, and
///    only the highest-priority one actually shows)
///  - packs disabled in scenery_packs.ini the user may have forgotten about
public struct DuplicateAnalyzer {
    let installation: Installation

    public init(installation: Installation) {
        self.installation = installation
    }

    public func analyze() -> (findings: [Finding], groups: [DuplicateGroup]) {
        var findings: [Finding] = []
        var groups: [DuplicateGroup] = []

        // ICAO -> packs providing it (custom, non-library, non-Laminar packs only;
        // overriding Global Airports is the whole point of add-on scenery).
        var byAirport: [String: [SceneryPack]] = [:]
        for pack in installation.packs where !pack.isLibrary && !pack.isLaminar {
            for icao in pack.airports.keys {
                byAirport[icao, default: []].append(pack)
            }
        }

        // Size on disk helps decide which duplicate to keep; compute once per
        // pack (the same pack can appear under several airports).
        var sizeCache: [String: Int64] = [:]
        func packSize(_ pack: SceneryPack) -> Int64 {
            if let cached = sizeCache[pack.name] { return cached }
            let size = DiskUsage.sizeOfDirectory(at: pack.url)
            sizeCache[pack.name] = size
            return size
        }

        for (icao, packs) in byAirport.sorted(by: { $0.key < $1.key }) where packs.count > 1 {
            // Sort by ini priority: lower index loads first and wins. Disabled
            // packs never load, so the effective winner is the first *enabled* one.
            let ordered = packs.sorted {
                ($0.iniIndex ?? Int.max, $0.name) < ($1.iniIndex ?? Int.max, $1.name)
            }
            let winner = ordered.first { $0.isEnabled } ?? ordered[0]
            let losers = ordered.filter { $0.name != winner.name }
            let name = winner.airports[icao]?.name ?? icao
            let enabledLosers = losers.filter { $0.isEnabled }

            groups.append(DuplicateGroup(
                icao: icao,
                airportName: name,
                packs: ordered.map { pack in
                    DuplicatePack(
                        name: pack.name,
                        path: pack.url.path,
                        status: pack.status,
                        iniIndex: pack.iniIndex,
                        isWinner: pack.name == winner.name,
                        sizeBytes: packSize(pack),
                        kind: pack.kind,
                        modifiedDate: (try? FileManager.default.attributesOfItem(atPath: pack.url.path))?[.modificationDate] as? Date
                    )
                }
            ))

            let severity: Severity = enabledLosers.isEmpty ? .info : .warning
            let loserList = losers
                .map { pack -> String in
                    switch pack.status {
                    case .enabled: return "'\(pack.name)'"
                    case .disabled: return "'\(pack.name)' (disabled)"
                    case .uninstalled: return "'\(pack.name)' (uninstalled)"
                    }
                }
                .joined(separator: ", ")

            findings.append(Finding(
                checkID: "DUP-01",
                severity: severity,
                category: .duplicatePackage,
                title: "\(icao) (\(name)) provided by \(packs.count) packages",
                detail: "'\(winner.name)' has the highest priority in scenery_packs.ini and is the one X-Plane shows. Also providing \(icao): \(loserList). Overlapping airport packs can conflict (double buildings, z-fighting pavement) and waste disk space.",
                path: winner.url.path,
                suggestion: enabledLosers.isEmpty
                    ? "The duplicates are disabled, so this is only wasted disk space. Delete the ones you don't use."
                    : "Keep the one you prefer and disable, move or trash the rest (select the packages in this list and use Actions).",
                fixability: .assisted,
                packName: winner.name,
                packKind: winner.kind
            ))
        }

        // Disabled packs reminder.
        let disabled = installation.packs.filter { !$0.isEnabled }
        if !disabled.isEmpty {
            let list = disabled.map { $0.name }.sorted().joined(separator: ", ")
            findings.append(Finding(
                checkID: "DUP-02",
                severity: .info,
                category: .duplicatePackage,
                title: "\(disabled.count) scenery pack\(disabled.count == 1 ? "" : "s") disabled in scenery_packs.ini",
                detail: "Disabled but still on disk: \(list).",
                suggestion: "If you no longer need them, deleting them frees disk space.",
                fixability: .assisted,
                relatedPacks: disabled
                    .sorted { $0.name < $1.name }
                    .map { Finding.RelatedPack(name: $0.name, path: $0.url.path) }
            ))
        }

        // Identical pack names differing only by case or trailing spaces — a
        // classic sign of a double-install from repeated unzipping. The SAME
        // spelling in two places (Custom Scenery + the disabled folder) lands
        // here too, so each folder's FULL PATH is the only way to tell the
        // copies apart — list and attach every one.
        var namesLowered: [String: [SceneryPack]] = [:]
        for pack in installation.packs {
            namesLowered[pack.name.lowercased().trimmingCharacters(in: .whitespaces), default: []]
                .append(pack)
        }
        for (_, variants) in namesLowered where variants.count > 1 {
            let ordered = variants.sorted { $0.url.path < $1.url.path }
            let pathList = ordered
                .map { pack -> String in
                    switch pack.status {
                    case .enabled: return "\(pack.url.path) (enabled)"
                    case .disabled: return "\(pack.url.path) (disabled in scenery_packs.ini)"
                    case .uninstalled: return "\(pack.url.path) (uninstalled)"
                    }
                }
                .joined(separator: "\n")
            findings.append(Finding(
                checkID: "DUP-03",
                severity: .warning,
                category: .duplicatePackage,
                title: "Near-identical pack folders: \(ordered.map { $0.name }.joined(separator: " / "))",
                detail: "These folder names are identical or differ only in case or whitespace — usually the same package installed twice (a re-download often lands beside the uninstalled copy):\n\(pathList)",
                suggestion: "Keep one copy and delete the other. Use the Reveal in Finder links below to inspect each folder before deciding.",
                fixability: .assisted,
                relatedPacks: ordered.map { Finding.RelatedPack(name: $0.name, path: $0.url.path) }
            ))
        }

        return (findings, groups)
    }
}
