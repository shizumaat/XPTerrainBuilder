import Foundation

/// User-invokable remediations for scenery packs.
public enum PackAction: String, CaseIterable, Sendable {
    case enable
    case disable
    case moveToDisabledFolder
    case trash

    public var label: String {
        switch self {
        case .enable: return "Enable"
        case .disable: return "Disable"
        case .moveToDisabledFolder: return "Move to Disabled Folder"
        case .trash: return "Move to Trash"
        }
    }
}

public struct PackActionOutcome: Sendable, Identifiable {
    public let id = UUID()
    public let packName: String
    public let success: Bool
    public let message: String?
}

/// Applies pack actions against a real installation.
///
/// - Disable/Enable rewrite the pack's line in scenery_packs.ini
///   (SCENERY_PACK ↔ SCENERY_PACK_DISABLED), which is exactly what X-Plane's
///   own UI does — files stay put.
/// - Move relocates the folder to "Custom Scenery (Disabled)" beside
///   Custom Scenery, so it survives X-Plane updates and is easy to restore.
/// - Trash uses the Finder Trash (recoverable), never direct deletion.
///
/// All edits preserve the rest of scenery_packs.ini untouched; X-Plane
/// re-adds any missing entries as enabled on next launch, so removing a
/// moved/trashed pack's line is safe.
public struct PackActionService {
    public let root: URL

    public init(root: URL) {
        self.root = root
    }

    var customSceneryURL: URL { root.appendingPathComponent("Custom Scenery") }
    var iniURL: URL { customSceneryURL.appendingPathComponent("scenery_packs.ini") }
    public var disabledFolderURL: URL { root.appendingPathComponent("Custom Scenery (Disabled)") }

    public func apply(_ action: PackAction, to packNames: [String]) -> [PackActionOutcome] {
        switch action {
        case .enable: return setEnabled(true, packNames)
        case .disable: return setEnabled(false, packNames)
        case .moveToDisabledFolder: return relocate(packNames)
        case .trash: return trash(packNames)
        }
    }

    // MARK: - scenery_packs.ini editing

    static let iniHeader = "I\n1000 Version\nSCENERY\n\n"

    /// The two path spellings X-Plane accepts for a pack line.
    static func iniPaths(for packName: String) -> [String] {
        ["Custom Scenery/\(packName)/", "Custom Scenery/\(packName)"]
    }

    static func packName(fromIniLine line: String) -> String? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        for keyword in ["SCENERY_PACK_DISABLED ", "SCENERY_PACK "] where trimmed.hasPrefix(keyword) {
            var path = String(trimmed.dropFirst(keyword.count)).trimmingCharacters(in: .whitespaces)
            if path.hasSuffix("/") { path.removeLast() }
            guard path.hasPrefix("Custom Scenery/") else { return nil }
            return String(path.dropFirst("Custom Scenery/".count))
        }
        return nil
    }

    /// Rewrite ini lines for the given packs. `keyword` nil removes the line.
    func rewriteIni(packNames: [String], keyword: String?) -> Error? {
        let names = Set(packNames)
        let text = TextFile.contents(of: iniURL) ?? Self.iniHeader
        var lines = text.components(separatedBy: "\n")
        var seen = Set<String>()

        lines = lines.compactMap { line -> String? in
            guard let name = Self.packName(fromIniLine: line), names.contains(name) else {
                return line
            }
            seen.insert(name)
            guard let keyword else { return nil } // remove
            return "\(keyword) Custom Scenery/\(name)/"
        }

        // Packs not yet listed (X-Plane hasn't run since they were added).
        if let keyword {
            for name in names.subtracting(seen).sorted() {
                lines.append("\(keyword) Custom Scenery/\(name)/")
            }
        }

        do {
            try lines.joined(separator: "\n")
                .write(to: iniURL, atomically: true, encoding: .utf8)
            return nil
        } catch {
            return error
        }
    }

    // MARK: - Actions

    func setEnabled(_ enabled: Bool, _ packNames: [String]) -> [PackActionOutcome] {
        if let error = rewriteIni(
            packNames: packNames,
            keyword: enabled ? "SCENERY_PACK" : "SCENERY_PACK_DISABLED"
        ) {
            return packNames.map {
                PackActionOutcome(packName: $0, success: false,
                                  message: "Could not update scenery_packs.ini: \(error.localizedDescription)")
            }
        }
        return packNames.map { PackActionOutcome(packName: $0, success: true, message: nil) }
    }

    func relocate(_ packNames: [String]) -> [PackActionOutcome] {
        let fm = FileManager.default
        var outcomes: [PackActionOutcome] = []
        var moved: [String] = []

        do {
            try fm.createDirectory(at: disabledFolderURL, withIntermediateDirectories: true)
        } catch {
            return packNames.map {
                PackActionOutcome(packName: $0, success: false,
                                  message: "Could not create \(disabledFolderURL.lastPathComponent): \(error.localizedDescription)")
            }
        }

        for name in packNames {
            let source = customSceneryURL.appendingPathComponent(name)
            let destination = disabledFolderURL.appendingPathComponent(name)
            guard fm.fileExists(atPath: source.path) else {
                outcomes.append(PackActionOutcome(packName: name, success: false, message: "Folder not found."))
                continue
            }
            guard !fm.fileExists(atPath: destination.path) else {
                outcomes.append(PackActionOutcome(packName: name, success: false,
                                                  message: "A folder with this name already exists in \(disabledFolderURL.lastPathComponent)."))
                continue
            }
            do {
                try fm.moveItem(at: source, to: destination)
                moved.append(name)
                outcomes.append(PackActionOutcome(packName: name, success: true, message: nil))
            } catch {
                outcomes.append(PackActionOutcome(packName: name, success: false,
                                                  message: error.localizedDescription))
            }
        }

        _ = rewriteIni(packNames: moved, keyword: nil)
        return outcomes
    }

    func trash(_ packNames: [String]) -> [PackActionOutcome] {
        let fm = FileManager.default
        var outcomes: [PackActionOutcome] = []
        var trashed: [String] = []

        for name in packNames {
            let source = customSceneryURL.appendingPathComponent(name)
            guard fm.fileExists(atPath: source.path) else {
                outcomes.append(PackActionOutcome(packName: name, success: false, message: "Folder not found."))
                continue
            }
            do {
                try fm.trashItem(at: source, resultingItemURL: nil)
                trashed.append(name)
                outcomes.append(PackActionOutcome(packName: name, success: true, message: nil))
            } catch {
                outcomes.append(PackActionOutcome(packName: name, success: false,
                                                  message: error.localizedDescription))
            }
        }

        _ = rewriteIni(packNames: trashed, keyword: nil)
        return outcomes
    }
}
