import Foundation

/// The resource definition tables of a DSF tile: every terrain, object,
/// polygon and network file the tile can reference. Paths are as written by
/// the compiler — pack-relative for local resources, virtual paths for
/// library ones.
public struct DSFDefinitions: Sendable {
    public var terrains: [String] = []
    public var objects: [String] = []
    public var polygons: [String] = []
    public var networks: [String] = []
    public var rasters: [String] = []
}

public enum DSFReadResult: Sendable {
    case ok(DSFDefinitions)
    case compressed      // 7z-compressed DSF; we don't decompress in v1
    case invalid
}

/// Reads just the DEFN atom of a DSF file.
///
/// DSF is `"XPLNEDSF" + int32 version`, then a sequence of atoms
/// `[4-byte id][int32 total length incl. 8-byte header]`, ending with a
/// 16-byte MD5 footer. The DEFN atom (subatoms TERT/OBJT/POLY/NETW/DEMN,
/// each a run of NUL-terminated strings) is a few KB near the front, so the
/// reader seeks over everything else — installs can hold >150k tiles and
/// whole-file reads would be hundreds of gigabytes.
public enum DSFReader {
    static let rawMagic = Data("XPLNEDSF".utf8)
    static let sevenZipMagic = Data([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])

    public static func readDefinitions(url: URL) -> DSFReadResult {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return .invalid }
        defer { try? handle.close() }
        guard let fileSize = (try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? Int,
              fileSize > 12 + 16
        else { return .invalid }

        guard let header = try? handle.read(upToCount: 12), header.count == 12 else { return .invalid }
        if header.starts(with: sevenZipMagic) { return .compressed }
        guard header.starts(with: rawMagic) else { return .invalid }

        let atomsEnd = fileSize - 16 // MD5 footer
        var offset = 12

        while offset + 8 <= atomsEnd {
            guard let atomHeader = try? handle.read(upToCount: 8), atomHeader.count == 8 else { return .invalid }
            let id = String(decoding: atomHeader.prefix(4), as: UTF8.self)
            let length = atomHeader.littleEndianInt32(at: 4)
            guard length >= 8, offset + length <= atomsEnd + 16 else { return .invalid }

            if id == "DEFN" || id == "NFED" {
                guard let body = try? handle.read(upToCount: length - 8), body.count == length - 8 else {
                    return .invalid
                }
                return .ok(parseDefinitionAtom(body))
            }

            offset += length
            do {
                try handle.seek(toOffset: UInt64(offset))
            } catch {
                return .invalid
            }
        }
        // No DEFN atom — structurally odd but not worth failing the pack over.
        return .ok(DSFDefinitions())
    }

    static func parseDefinitionAtom(_ body: Data) -> DSFDefinitions {
        var defs = DSFDefinitions()
        var offset = 0
        let bytes = [UInt8](body)

        while offset + 8 <= bytes.count {
            let id = String(decoding: bytes[offset..<offset + 4], as: UTF8.self)
            let length = Int(bytes[offset + 4])
                | (Int(bytes[offset + 5]) << 8)
                | (Int(bytes[offset + 6]) << 16)
                | (Int(bytes[offset + 7]) << 24)
            guard length >= 8, offset + length <= bytes.count else { break }

            let strings = parseStringTable(bytes[(offset + 8)..<(offset + length)])
            switch id {
            case "TERT", "TRET": defs.terrains = strings
            case "OBJT", "TJBO": defs.objects = strings
            case "POLY", "YLOP": defs.polygons = strings
            case "NETW", "WTEN": defs.networks = strings
            case "DEMN", "NMED": defs.rasters = strings
            default: break
            }
            offset += length
        }
        return defs
    }

    static func parseStringTable(_ slice: ArraySlice<UInt8>) -> [String] {
        var strings: [String] = []
        var current: [UInt8] = []
        for byte in slice {
            if byte == 0 {
                if !current.isEmpty {
                    strings.append(String(decoding: current, as: UTF8.self))
                    current = []
                }
            } else {
                current.append(byte)
            }
        }
        if !current.isEmpty {
            strings.append(String(decoding: current, as: UTF8.self))
        }
        return strings
    }
}

extension Data {
    func littleEndianInt32(at offset: Int) -> Int {
        guard count >= offset + 4 else { return 0 }
        return Int(self[startIndex + offset])
            | (Int(self[startIndex + offset + 1]) << 8)
            | (Int(self[startIndex + offset + 2]) << 16)
            | (Int(self[startIndex + offset + 3]) << 24)
    }
}
