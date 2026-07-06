import Foundation

// MARK: - LOD distance heuristic

public enum LODAdvisor {
    /// Far-cull distance appropriate for an object's physical size.
    ///
    /// An object stops being visually meaningful once it subtends a couple of
    /// pixels; at typical fields of view and resolutions that happens at
    /// roughly 100× its largest dimension. Clamped so ground clutter still
    /// survives a normal pattern circuit (300 m floor) and skyscrapers don't
    /// draw across half a continent (15 km ceiling), then rounded to a tidy
    /// number.
    public static func farCullDistance(forLargestDimension dimension: Double?) -> Int {
        guard let dimension, dimension.isFinite, dimension > 0 else { return 2000 }
        let raw = dimension * 100
        let clamped = min(max(raw, 300), 15_000)
        return Int((clamped / 100).rounded()) * 100
    }
}

// MARK: - Modification log

/// One file we modified, with everything needed to undo it.
public struct ModificationRecord: Codable, Identifiable, Sendable, Hashable {
    public let id: UUID
    public let date: Date
    /// Where the content lived before the change (revert target).
    public let filePath: String
    /// Where the original content lives now (sidecar backup, Trash location,
    /// or the renamed file itself).
    public let backupPath: String
    /// A file the fix created that revert should delete (e.g. the .dds
    /// produced by a PNG conversion).
    public let createdPath: String?
    public let checkID: String
    public let summary: String

    public init(filePath: String, backupPath: String, createdPath: String? = nil,
                checkID: String, summary: String) {
        self.id = UUID()
        self.date = Date()
        self.filePath = filePath
        self.backupPath = backupPath
        self.createdPath = createdPath
        self.checkID = checkID
        self.summary = summary
    }
}

/// JSON manifest of every file the app has modified. Lives in Application
/// Support so it survives across scenery re-installs and app updates.
public struct ModificationLog: Sendable {
    public let fileURL: URL

    public init(fileURL: URL) {
        self.fileURL = fileURL
    }

    public static func defaultURL() -> URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("XPSceneryDoctor", isDirectory: true)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("modifications.json")
    }

    public func load() -> [ModificationRecord] {
        guard let data = try? Data(contentsOf: fileURL) else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return (try? decoder.decode([ModificationRecord].self, from: data)) ?? []
    }

    public func save(_ records: [ModificationRecord]) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(records).write(to: fileURL, options: .atomic)
    }
}

// MARK: - Fix engine

public struct FixOutcome: Sendable, Identifiable {
    public let id = UUID()
    public let findingID: UUID
    public let filePath: String
    public let success: Bool
    public let message: String?
}

public struct RevertOutcome: Sendable, Identifiable {
    public let id = UUID()
    public let record: ModificationRecord
    public let success: Bool
    public let message: String?
}

/// Applies ProposedFixes and reverts them.
///
/// Contract (mirrors the xpsan spec's fixer rules):
/// - Before any edit, the original is copied to `<file>.xpsd-backup` next to
///   it and a ModificationRecord is written to the manifest. An existing
///   backup is never overwritten — the first backup is the true original.
/// - Edits are byte-level (no re-encoding of the untouched parts).
/// - After editing, the result is re-parsed to prove the fix took and nothing
///   else changed; on any doubt the backup is restored automatically.
public struct FixEngine: Sendable {
    public static let backupSuffix = ".xpsd-backup"

    public let log: ModificationLog

    public init(log: ModificationLog = ModificationLog(fileURL: ModificationLog.defaultURL())) {
        self.log = log
    }

    // MARK: Apply

    public func apply(_ findings: [Finding]) -> [FixOutcome] {
        var records = log.load()
        var outcomes: [FixOutcome] = []

        for finding in findings {
            guard let fix = finding.proposedFix else { continue }
            let outcome = applySingle(fix, finding: finding, records: &records)
            outcomes.append(outcome)
        }

        try? log.save(records)
        return outcomes
    }

    func applySingle(_ fix: ProposedFix, finding: Finding, records: inout [ModificationRecord]) -> FixOutcome {
        switch fix {
        case .addFarLOD:
            return applyFarLOD(fix, finding: finding, records: &records)
        case .renameFile(let fromPath, let toPath):
            return applyRename(fromPath: fromPath, toPath: toPath, finding: finding, records: &records)
        case .convertPNGToDDS(let pngPath):
            return applyPNGConversion(pngPath: pngPath, finding: finding, records: &records)
        case .promoteGlobalNoBlend(let objPath):
            return applyGlobalPromotion(objPath: objPath, finding: finding, records: &records)
        }
    }

    // MARK: promoteGlobalNoBlend

    /// Remove uniform per-mesh ATTR_no_blend lines and declare
    /// GLOBAL_no_blend in the header, restoring the instanced drawing path.
    func applyGlobalPromotion(objPath: String, finding: Finding,
                              records: inout [ModificationRecord]) -> FixOutcome {
        let fm = FileManager.default
        let fileURL = URL(fileURLWithPath: objPath)
        let backupURL = URL(fileURLWithPath: objPath + Self.backupSuffix)

        func fail(_ message: String) -> FixOutcome {
            FixOutcome(findingID: finding.id, filePath: objPath, success: false, message: message)
        }

        guard let original = try? Data(contentsOf: fileURL) else {
            return fail("Could not read the file.")
        }
        let before = ObjParser.parse(data: original)
        guard before.perMeshNoBlend > 0, before.blendStateChanges == 0,
              !before.hasGlobalNoBlend, !before.animated else {
            return fail("The object's blend state is not uniformly promotable.")
        }

        // Byte-level edit: drop ATTR_no_blend lines; insert GLOBAL_no_blend
        // before the first draw command (the header ends there).
        guard let text = String(data: original, encoding: .utf8)
                ?? String(data: original, encoding: .isoLatin1) else {
            return fail("Could not decode the file.")
        }
        let kept = text.components(separatedBy: "\n").filter {
            !$0.trimmingCharacters(in: .whitespaces).hasPrefix("ATTR_no_blend")
        }
        let rejoined = Data(kept.joined(separator: "\n").utf8)
        guard let edited = Self.insertHeaderDirective("GLOBAL_no_blend", into: rejoined) else {
            return fail("No draw commands found — not a valid OBJ8 file?")
        }

        let after = ObjParser.parse(data: edited)
        guard after.perMeshNoBlend == 0, after.hasGlobalNoBlend,
              after.vertexCount == before.vertexCount else {
            return fail("Edited file failed validation; no changes were made.")
        }

        if !fm.fileExists(atPath: backupURL.path) {
            do { try original.write(to: backupURL, options: .atomic) }
            catch { return fail("Could not create backup: \(error.localizedDescription)") }
        }
        do { try edited.write(to: fileURL, options: .atomic) }
        catch { return fail("Could not write the file: \(error.localizedDescription)") }

        if !records.contains(where: { $0.filePath == objPath }) {
            records.append(ModificationRecord(
                filePath: objPath, backupPath: backupURL.path,
                checkID: finding.checkID, summary: "Promoted ATTR_no_blend to GLOBAL_no_blend"
            ))
        }
        return FixOutcome(findingID: finding.id, filePath: objPath, success: true, message: nil)
    }

    /// Insert a header directive before the first draw command — same anchor
    /// rule as the LOD fixer.
    static func insertHeaderDirective(_ directive: String, into data: Data) -> Data? {
        guard let insertAt = firstCommandOffset(in: data) else { return nil }
        var result = Data()
        result.append(data.prefix(insertAt))
        result.append(Data("\(directive)\n".utf8))
        result.append(data.suffix(from: insertAt))
        return result
    }

    // MARK: addFarLOD

    func applyFarLOD(_ fix: ProposedFix, finding: Finding, records: inout [ModificationRecord]) -> FixOutcome {
        let fm = FileManager.default
        let filePath = fix.targetPath
        let fileURL = URL(fileURLWithPath: filePath)
        let backupURL = URL(fileURLWithPath: filePath + Self.backupSuffix)

        func fail(_ message: String) -> FixOutcome {
            FixOutcome(findingID: finding.id, filePath: filePath, success: false, message: message)
        }

        guard let original = try? Data(contentsOf: fileURL) else {
            return fail("Could not read the file.")
        }

        // Compute the edited bytes.
        let edited: Data
        switch fix {
        case .addFarLOD(_, let distance):
            let before = ObjParser.parse(data: original)
            guard !before.hasLOD else {
                return fail("The object already has an ATTR_LOD.")
            }
            guard let inserted = Self.insertFarLOD(into: original, distanceMeters: distance) else {
                return fail("No draw commands found — not a valid OBJ8 file?")
            }
            // Validate: LOD present, geometry untouched.
            let after = ObjParser.parse(data: inserted)
            guard after.hasLOD, after.vertexCount == before.vertexCount else {
                return fail("Edited file failed validation; no changes were made.")
            }
            edited = inserted
        default:
            return fail("Internal error: wrong fixer.")
        }

        // Back up the original (first backup wins — it is the true original).
        if !fm.fileExists(atPath: backupURL.path) {
            do {
                try original.write(to: backupURL, options: .atomic)
            } catch {
                return fail("Could not create backup: \(error.localizedDescription)")
            }
        }

        do {
            try edited.write(to: fileURL, options: .atomic)
        } catch {
            return fail("Could not write the file: \(error.localizedDescription)")
        }

        // Only log once per file; a re-fix after revert gets a fresh record.
        if !records.contains(where: { $0.filePath == filePath }) {
            records.append(ModificationRecord(
                filePath: filePath,
                backupPath: backupURL.path,
                checkID: finding.checkID,
                summary: fix.summary
            ))
        }
        return FixOutcome(findingID: finding.id, filePath: filePath, success: true, message: nil)
    }

    // MARK: renameFile

    /// Rename an encoding-damaged file or folder to the referenced spelling.
    /// The record stores the old path as `filePath` and the new path as
    /// `backupPath`, so the standard move-based revert renames it back.
    func applyRename(fromPath: String, toPath: String, finding: Finding,
                     records: inout [ModificationRecord]) -> FixOutcome {
        let fm = FileManager.default

        func fail(_ message: String) -> FixOutcome {
            FixOutcome(findingID: finding.id, filePath: fromPath, success: false, message: message)
        }

        guard fm.fileExists(atPath: fromPath) else {
            return fail("File not found — was it already renamed?")
        }
        guard !fm.fileExists(atPath: toPath) else {
            return fail("A file with the corrected name already exists.")
        }
        do {
            try fm.moveItem(atPath: fromPath, toPath: toPath)
        } catch {
            return fail(error.localizedDescription)
        }
        guard fm.fileExists(atPath: toPath) else {
            return fail("Rename did not take effect.")
        }
        records.append(ModificationRecord(
            filePath: fromPath,
            backupPath: toPath,
            checkID: finding.checkID,
            summary: "Renamed '\(URL(fileURLWithPath: fromPath).lastPathComponent)' → '\(URL(fileURLWithPath: toPath).lastPathComponent)'"
        ))
        return FixOutcome(findingID: finding.id, filePath: fromPath, success: true, message: nil)
    }

    // MARK: convertPNGToDDS

    /// Encode the PNG as a mipmapped BC1/BC3 DDS next to it, then retire the
    /// PNG to a sidecar backup. X-Plane resolves "foo.png" references to
    /// foo.dds automatically, so no referencing file needs editing.
    func applyPNGConversion(pngPath: String, finding: Finding,
                            records: inout [ModificationRecord]) -> FixOutcome {
        let fm = FileManager.default
        let pngURL = URL(fileURLWithPath: pngPath)
        let ddsURL = pngURL.deletingPathExtension().appendingPathExtension("dds")
        let backupURL = URL(fileURLWithPath: pngPath + Self.backupSuffix)

        func fail(_ message: String) -> FixOutcome {
            FixOutcome(findingID: finding.id, filePath: pngPath, success: false, message: message)
        }

        guard fm.fileExists(atPath: pngPath) else { return fail("File not found.") }
        guard !fm.fileExists(atPath: ddsURL.path) else {
            return fail("A .dds with this name already exists — X-Plane is already using it.")
        }

        let ddsData: Data
        switch DDSEncoder.encodePNG(at: pngURL) {
        case .success(let data): ddsData = data
        case .failure(let error): return fail(error.description)
        }

        do {
            try ddsData.write(to: ddsURL, options: .atomic)
        } catch {
            return fail("Could not write DDS: \(error.localizedDescription)")
        }

        // Validate the result before touching the PNG.
        guard let info = TextureInspector.inspect(url: ddsURL),
              info.format == .dds, info.width > 0, info.mipMapCount > 1 else {
            try? fm.removeItem(at: ddsURL)
            return fail("Encoded DDS failed validation; no changes were made.")
        }

        do {
            try fm.moveItem(at: pngURL, to: backupURL)
        } catch {
            try? fm.removeItem(at: ddsURL)
            return fail("Could not retire the PNG: \(error.localizedDescription)")
        }

        records.append(ModificationRecord(
            filePath: pngPath,
            backupPath: backupURL.path,
            createdPath: ddsURL.path,
            checkID: finding.checkID,
            summary: "Converted to DDS (\(info.width)×\(info.height), \(info.mipMapCount) mips)"
        ))
        return FixOutcome(findingID: finding.id, filePath: pngPath, success: true, message: nil)
    }

    /// Insert `ATTR_LOD 0 <distance>` immediately before the first drawing
    /// command (TRIS/LINES/lights/animation), so every draw command falls
    /// inside the 0..<distance LOD range. Header attributes like
    /// ATTR_layer_group are deliberately NOT insertion anchors — they can
    /// appear before the data section, and ATTR_LOD must not. State-setting
    /// ATTRs ahead of the inserted line are legal initial state. Byte-level:
    /// untouched lines are preserved exactly.
    static func insertFarLOD(into data: Data, distanceMeters: Int) -> Data? {
        insertHeaderDirective("ATTR_LOD 0 \(distanceMeters)", into: data)
    }

    /// Byte offset of the first drawing command line (TRIS/LINES/lights/
    /// animation) — header attributes are deliberately not anchors.
    static func firstCommandOffset(in data: Data) -> Int? {
        let commandPrefixes: [[UInt8]] = [
            Array("TRIS".utf8), Array("LINES".utf8), Array("LIGHT".utf8),
            Array("ANIM".utf8), Array("EMITTER".utf8), Array("SMOKE_".utf8),
        ]

        var insertOffset: Int? = nil
        data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            guard let base = raw.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return }
            let count = raw.count
            var i = 0
            while i < count {
                var j = i
                while j < count && base[j] != 0x0A { j += 1 }
                var start = i
                while start < j && (base[start] == 0x20 || base[start] == 0x09) { start += 1 }
                for prefix in commandPrefixes where j - start >= prefix.count {
                    if memcmp(base + start, prefix, prefix.count) == 0 {
                        insertOffset = i
                        return
                    }
                }
                i = j + 1
            }
        }
        return insertOffset
    }

    // MARK: Trash (unused resources)

    /// Move files to the Finder Trash, recording each in the manifest so the
    /// Modifications window can restore it (backupPath = its Trash location).
    public func trashFiles(_ paths: [String], checkID: String, summary: String) -> [FixOutcome] {
        let fm = FileManager.default
        var records = log.load()
        var outcomes: [FixOutcome] = []

        for path in paths {
            let url = URL(fileURLWithPath: path)
            guard fm.fileExists(atPath: path) else {
                outcomes.append(FixOutcome(findingID: UUID(), filePath: path, success: false,
                                           message: "File not found."))
                continue
            }
            var trashedURL: NSURL?
            do {
                try fm.trashItem(at: url, resultingItemURL: &trashedURL)
                if let trashedPath = trashedURL?.path {
                    records.append(ModificationRecord(
                        filePath: path,
                        backupPath: trashedPath,
                        checkID: checkID,
                        summary: summary
                    ))
                }
                outcomes.append(FixOutcome(findingID: UUID(), filePath: path, success: true, message: nil))
            } catch {
                outcomes.append(FixOutcome(findingID: UUID(), filePath: path, success: false,
                                           message: error.localizedDescription))
            }
        }

        try? log.save(records)
        return outcomes
    }

    // MARK: Revert

    /// Moves the backup over the current file. Move (not byte copy): trashed
    /// ortho textures run to gigabytes.
    public func revert(_ toRevert: [ModificationRecord]) -> [RevertOutcome] {
        let fm = FileManager.default
        var records = log.load()
        var outcomes: [RevertOutcome] = []

        for record in toRevert {
            let backupURL = URL(fileURLWithPath: record.backupPath)
            let fileURL = URL(fileURLWithPath: record.filePath)

            guard fm.fileExists(atPath: backupURL.path) else {
                outcomes.append(RevertOutcome(record: record, success: false,
                                              message: "Backup file is missing."))
                continue
            }
            do {
                if fm.fileExists(atPath: fileURL.path) {
                    try fm.removeItem(at: fileURL)
                }
                try fm.createDirectory(at: fileURL.deletingLastPathComponent(),
                                       withIntermediateDirectories: true)
                try fm.moveItem(at: backupURL, to: fileURL)
                if let created = record.createdPath {
                    try? fm.removeItem(atPath: created)
                }
                records.removeAll { $0.id == record.id }
                outcomes.append(RevertOutcome(record: record, success: true, message: nil))
            } catch {
                outcomes.append(RevertOutcome(record: record, success: false,
                                              message: error.localizedDescription))
            }
        }

        try? log.save(records)
        return outcomes
    }
}
