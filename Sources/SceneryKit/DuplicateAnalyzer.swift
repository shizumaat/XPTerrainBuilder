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
            let name = winner.airports[icao] ?? icao
            let enabledLosers = losers.filter { $0.isEnabled }

            groups.append(DuplicateGroup(
                icao: icao,
                airportName: name,
                packs: ordered.map { pack in
                    DuplicatePack(
                        name: pack.name,
                        path: pack.url.path,
                        isEnabled: pack.isEnabled,
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
                .map { "'\($0.name)'\($0.isEnabled ? "" : " (disabled)")" }
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
                fixability: .assisted
            ))
        }

        // Identical pack names differing only by case or trailing spaces — a
        // classic sign of a double-install from repeated unzipping.
        var namesLowered: [String: [String]] = [:]
        for pack in installation.packs {
            namesLowered[pack.name.lowercased().trimmingCharacters(in: .whitespaces), default: []]
                .append(pack.name)
        }
        for (_, variants) in namesLowered where variants.count > 1 {
            findings.append(Finding(
                checkID: "DUP-03",
                severity: .warning,
                category: .duplicatePackage,
                title: "Near-identical pack folders: \(variants.sorted().joined(separator: " / "))",
                detail: "These folder names differ only in case or whitespace — usually the same package installed twice.",
                suggestion: "Keep one copy and delete the other.",
                fixability: .assisted
            ))
        }

        return (findings, groups)
    }
}
