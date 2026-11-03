import Foundation

/// Reads and repairs scenery_packs.ini against what is actually in Custom
/// Scenery, so the map's load order and enabled/disabled state match reality
/// between X-Plane launches.
///
/// Edits preserve the rest of the file untouched; X-Plane re-adds any missing
/// entries as enabled on its next launch, so removing a vanished pack's line
/// is safe.
public struct PackActionService {
    public let root: URL

    public init(root: URL) {
        self.root = root
    }

    var customSceneryURL: URL { root.appendingPathComponent("Custom Scenery") }
    var iniURL: URL { customSceneryURL.appendingPathComponent("scenery_packs.ini") }
    public var disabledFolderURL: URL { root.appendingPathComponent("Custom Scenery (Disabled)") }

    // MARK: - scenery_packs.ini editing

    static let iniHeader = "I\n1000 Version\nSCENERY\n\n"

    static func packName(fromIniLine line: String) -> String? {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        for keyword in ["SCENERY_PACK_DISABLED ", "SCENERY_PACK "] where trimmed.hasPrefix(keyword) {
            var path = String(trimmed.dropFirst(keyword.count)).trimmingCharacters(in: .whitespaces)
            if path.hasSuffix("/") { path.removeLast() }
            guard path.hasPrefix("Custom Scenery/") else { return nil }
            return String(path.dropFirst("Custom Scenery/".count))
        }
        return nil
    }

    // MARK: - Folder ↔ ini reconciliation

    /// What reconcile did to scenery_packs.ini.
    public struct IniReconciliation: Sendable {
        public var added: [String] = []
        public var removed: [String] = []
        public var renamed: [String] = []   // "old → new"
        public var writeError: String? = nil
        public var changed: Bool { !(added.isEmpty && removed.isEmpty && renamed.isEmpty) }
    }

    /// Synchronize scenery_packs.ini with what is ACTUALLY in Custom
    /// Scenery — X-Plane only does this on its own next launch, so folders
    /// added, removed or renamed in Finder would otherwise sit misrepresented
    /// until then.
    ///
    /// - Deleted folder → its line is removed.
    /// - New folder → left to the ENGINE's `tidy_scenery_packs`
    ///   (`O4_Scenery_Packs_Tidy.py`, the rule the Qt window runs too),
    ///   which files it in its kind's group, meshes below every ortho;
    ///   AnalysisController calls it right after this.
    /// - Renamed folder (same content signature reappearing under a new
    ///   name) → the existing line is rewritten IN PLACE, preserving its
    ///   position and enabled/disabled state.
    public func reconcile(installedPacks: [SceneryPack],
                          previousPacks: [SceneryPack]) -> IniReconciliation {
        let installed = installedPacks.filter { $0.isInstalled }
        let text = TextFile.contents(of: iniURL) ?? Self.iniHeader
        var lines = text.components(separatedBy: "\n")
        var result = IniReconciliation()

        var lineIndexByName: [String: Int] = [:]
        for (i, line) in lines.enumerated() {
            if let name = Self.packName(fromIniLine: line), lineIndexByName[name] == nil {
                lineIndexByName[name] = i
            }
        }
        let installedNames = Set(installed.map { $0.name })
        var toRemove = Set(lineIndexByName.keys).subtracting(installedNames)
        // Unlisted names, for the rename match only.
        var toAdd = installedNames.subtracting(lineIndexByName.keys)

        // Renames first: content signatures survive a folder rename, so a
        // vanished name whose signature reappears under exactly one new name
        // keeps its slot and keyword.
        if !toRemove.isEmpty, !toAdd.isEmpty {
            let previousSignatures = Dictionary(
                previousPacks.filter { $0.isInstalled && !$0.signature.isEmpty }
                    .map { ($0.name, $0.signature) },
                uniquingKeysWith: { first, _ in first })
            var addedBySignature: [String: [String]] = [:]
            for pack in installed where toAdd.contains(pack.name) && !pack.signature.isEmpty {
                addedBySignature[pack.signature, default: []].append(pack.name)
            }
            for old in toRemove.sorted() {
                guard let oldSignature = previousSignatures[old],
                      let matches = addedBySignature[oldSignature], matches.count == 1,
                      let new = matches.first, toAdd.contains(new),
                      let slot = lineIndexByName[old] else { continue }
                let wasDisabled = lines[slot].trimmingCharacters(in: .whitespaces)
                    .hasPrefix("SCENERY_PACK_DISABLED")
                lines[slot] = "\(wasDisabled ? "SCENERY_PACK_DISABLED" : "SCENERY_PACK") Custom Scenery/\(new)/"
                toRemove.remove(old)
                toAdd.remove(new)
                result.renamed.append("\(old) → \(new)")
            }
        }

        if !toRemove.isEmpty {
            lines = lines.filter { line in
                guard let name = Self.packName(fromIniLine: line) else { return true }
                return !toRemove.contains(name)
            }
            result.removed = toRemove.sorted()
        }

        guard result.changed else { return result }
        // The user's ini is kept once, before this app first changes it
        // (`O4_Scenery_Packs.write_ini_lines`, the same name).
        let backup = iniURL.appendingPathExtension("o4bak")
        if FileManager.default.fileExists(atPath: iniURL.path),
           !FileManager.default.fileExists(atPath: backup.path) {
            try? FileManager.default.copyItem(at: iniURL, to: backup)
        }
        do {
            try lines.joined(separator: "\n")
                .write(to: iniURL, atomically: true, encoding: .utf8)
        } catch {
            result.writeError = error.localizedDescription
        }
        return result
    }

    /// Enabled flag per listed pack, for cheap status refreshes after our
    /// own ini edits.
    public func iniStatuses() -> [String: Bool] {
        guard let text = TextFile.contents(of: iniURL) else { return [:] }
        var statuses: [String: Bool] = [:]
        for line in TextFile.lines(text) {
            let string = String(line)
            guard let name = Self.packName(fromIniLine: string), statuses[name] == nil else { continue }
            statuses[name] = !string.trimmingCharacters(in: .whitespaces)
                .hasPrefix("SCENERY_PACK_DISABLED")
        }
        return statuses
    }

    /// Current ini rank of every listed pack (line order, 0-based) — a cheap
    /// way to refresh display order after a reorder without a full rescan.
    public func iniOrder() -> [String: Int] {
        guard let text = TextFile.contents(of: iniURL) else { return [:] }
        var order: [String: Int] = [:]
        var rank = 0
        for line in TextFile.lines(text) {
            guard let name = Self.packName(fromIniLine: String(line)) else { continue }
            if order[name] == nil { order[name] = rank }
            rank += 1
        }
        return order
    }
}
