import Foundation

/// Walks an X-Plane root folder and builds the in-memory model every
/// analyzer works from: the list of scenery packs (with their airports,
/// enabled state and load order) plus the merged library export index.
public struct InstallationScanner {
    let root: URL
    let fm = FileManager.default

    public init(root: URL) {
        self.root = root
    }

    public func scan() -> Installation {
        let customScenery = root.appendingPathComponent("Custom Scenery")
        let iniOrder = parseSceneryPacksIni(customScenery.appendingPathComponent("scenery_packs.ini"))

        var packs: [SceneryPack] = []
        var libraryIndex = LibraryIndex()

        let contents = (try? fm.contentsOfDirectory(
            at: customScenery,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        )) ?? []

        for url in contents.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            guard (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true else { continue }
            let name = url.lastPathComponent
            let isLibrary = fm.fileExists(atPath: url.appendingPathComponent("library.txt").path)
            if isLibrary {
                libraryIndex.indexLibrary(at: url, packName: name)
            }
            let airports = parseAirports(inPack: url)
            let iniKey = "Custom Scenery/\(name)/"
            let iniEntry = iniOrder[iniKey] ?? iniOrder["Custom Scenery/\(name)"]
            let hasDSF = packContainsDSF(url)
            packs.append(SceneryPack(
                name: name,
                url: url,
                isEnabled: iniEntry?.enabled ?? true, // not listed yet = will be added enabled on next launch
                iniIndex: iniEntry?.index,
                isLibrary: isLibrary,
                airports: airports,
                hasDSF: hasDSF,
                isLaminar: Self.laminarPackNames.contains(name)
            ))
        }

        return Installation(root: root, packs: packs, libraryIndex: libraryIndex)
    }

    static let laminarPackNames: Set<String> = [
        "Global Airports",
        "X-Plane Landmarks - Chicago",
        "X-Plane Landmarks - Dubai",
        "X-Plane Landmarks - Las Vegas",
        "X-Plane Landmarks - London",
        "X-Plane Landmarks - New York",
        "X-Plane Landmarks - Rio de Janeiro",
        "X-Plane Landmarks - Sydney",
        "X-Plane Landmarks - Washington DC",
        "Aerosoft - EDDF Frankfurt", // XP11 bundled demo areas are left alone too
    ]

    struct IniEntry {
        let index: Int
        let enabled: Bool
    }

    /// scenery_packs.ini: one `SCENERY_PACK <path>/` or `SCENERY_PACK_DISABLED <path>/`
    /// per line, in load-priority order (first wins).
    func parseSceneryPacksIni(_ url: URL) -> [String: IniEntry] {
        guard let text = try? String(contentsOf: url, encoding: .utf8) else { return [:] }
        var result: [String: IniEntry] = [:]
        var index = 0
        for rawLine in text.split(separator: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            let enabled: Bool
            let path: String
            if line.hasPrefix("SCENERY_PACK_DISABLED ") {
                enabled = false
                path = String(line.dropFirst("SCENERY_PACK_DISABLED ".count))
            } else if line.hasPrefix("SCENERY_PACK ") {
                enabled = true
                path = String(line.dropFirst("SCENERY_PACK ".count))
            } else {
                continue
            }
            result[path.trimmingCharacters(in: .whitespaces)] = IniEntry(index: index, enabled: enabled)
            index += 1
        }
        return result
    }

    /// Parse the pack's apt.dat (if any) and return ICAO -> airport name.
    /// Airport headers are row codes 1 (land), 16 (seaplane), 17 (heliport):
    ///   `1 433 0 0 KSEA Seattle Tacoma Intl`
    /// XP11+ adds `1302 icao_code KSEA` metadata which takes precedence.
    func parseAirports(inPack packURL: URL) -> [String: String] {
        let candidates = [
            packURL.appendingPathComponent("Earth nav data/apt.dat"),
            packURL.appendingPathComponent("Earth Nav Data/apt.dat"),
        ]
        guard let aptURL = candidates.first(where: { fm.fileExists(atPath: $0.path) }) else {
            return [:]
        }
        guard let text = try? String(contentsOf: aptURL, encoding: .utf8) else { return [:] }

        var airports: [String: String] = [:]
        var currentID: String?
        var currentName: String?
        var currentICAOOverride: String?

        func flush() {
            if let id = currentICAOOverride ?? currentID {
                airports[id] = currentName ?? id
            }
            currentID = nil
            currentName = nil
            currentICAOOverride = nil
        }

        for rawLine in text.split(separator: "\n", omittingEmptySubsequences: true) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            let parts = line.split(separator: " ", omittingEmptySubsequences: true)
            guard let code = parts.first else { continue }
            switch code {
            case "1", "16", "17":
                flush()
                if parts.count >= 5 {
                    currentID = String(parts[4])
                    currentName = parts[5...].joined(separator: " ")
                }
            case "1302":
                if parts.count >= 3, parts[1] == "icao_code" {
                    currentICAOOverride = String(parts[2])
                }
            case "99":
                flush()
            default:
                break
            }
        }
        flush()
        return airports
    }

    func packContainsDSF(_ packURL: URL) -> Bool {
        let earthNav = packURL.appendingPathComponent("Earth nav data")
        guard let enumerator = fm.enumerator(
            at: earthNav,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else { return false }
        for case let file as URL in enumerator {
            if file.pathExtension.lowercased() == "dsf" { return true }
        }
        return false
    }
}
