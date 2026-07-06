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
    public let filePath: String
    public let backupPath: String
    public let checkID: String
    public let summary: String

    public init(filePath: String, backupPath: String, checkID: String, summary: String) {
        self.id = UUID()
        self.date = Date()
        self.filePath = filePath
        self.backupPath = backupPath
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

    /// Insert `ATTR_LOD 0 <distance>` immediately before the first drawing
    /// command (TRIS/LINES/lights/animation), so every draw command falls
    /// inside the 0..<distance LOD range. Header attributes like
    /// ATTR_layer_group are deliberately NOT insertion anchors — they can
    /// appear before the data section, and ATTR_LOD must not. State-setting
    /// ATTRs ahead of the inserted line are legal initial state. Byte-level:
    /// untouched lines are preserved exactly.
    static func insertFarLOD(into data: Data, distanceMeters: Int) -> Data? {
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

        guard let offset = insertOffset else { return nil }
        var result = Data()
        result.append(data.prefix(offset))
        result.append(Data("ATTR_LOD 0 \(distanceMeters)\n".utf8))
        result.append(data.suffix(from: offset))
        return result
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
