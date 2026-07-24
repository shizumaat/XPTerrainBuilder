import Foundation

/// One airport from X-Plane's Global Airports `apt.dat` — enough to search
/// and locate every airport in the world, not just installed custom scenery.
public struct GlobalAirport: Codable, Sendable, Equatable {
    public let id: String        // ICAO/ident column of the apt.dat header row
    public let name: String
    public let latitude: Double
    public let longitude: Double
    public init(id: String, name: String, latitude: Double, longitude: Double) {
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
    }
}

/// Streaming parser, JSON cache, and ranked search for the Global Airports
/// `apt.dat`. The file is hundreds of MB, so parsing never loads it whole:
/// it reads fixed-size chunks over a `FileHandle`, splits on newlines, and
/// decodes each line's bytes lossily (invalid UTF-8 → U+FFFD) so a single
/// Latin-1 airport name can't kill the parse. Malformed rows are skipped,
/// never thrown.
public enum GlobalAirportIndex {

    // MARK: - Parse

    /// Parse one apt.dat file into airports. Never throws on malformed
    /// rows — skip them; returns [] if the file is unreadable.
    public static func parse(aptDatURL: URL) -> [GlobalAirport] {
        guard let handle = try? FileHandle(forReadingFrom: aptDatURL) else { return [] }
        defer { try? handle.close() }

        var airports: [GlobalAirport] = []

        // Current airport block state.
        var haveHeader = false
        var id = ""
        var name = ""
        var datumLat: Double? = nil
        var datumLon: Double? = nil
        var fallbackLat: Double? = nil    // first coord pair from a 100/101/102 row
        var fallbackLon: Double? = nil

        func flush() {
            defer {
                haveHeader = false; id = ""; name = ""
                datumLat = nil; datumLon = nil; fallbackLat = nil; fallbackLon = nil
            }
            guard haveHeader, !id.isEmpty else { return }
            // Datum metadata wins; otherwise the first coordinate in the block.
            guard let lat = datumLat ?? fallbackLat,
                  let lon = datumLon ?? fallbackLon else { return }
            airports.append(GlobalAirport(id: id, name: name, latitude: lat, longitude: lon))
        }

        func handleLine(_ line: String) {
            // Trailing CR (CRLF files) is stripped by treating \r as a
            // field separator below.
            guard !line.isEmpty else { return }
            let fields = line.split(whereSeparator: {
                $0 == " " || $0 == "\t" || $0 == "\r" || $0 == "\n"
            })
            guard let code = fields.first else { return }

            switch code {
            case "1", "16", "17":
                // Header: `<code> <elev> <dep> <dep> <ident> <name...>`
                flush()
                guard fields.count >= 5 else { return }   // no ident → skip block
                id = String(fields[4])
                name = fields.count > 5 ? fields[5...].joined(separator: " ") : ""
                haveHeader = true

            case "1302":
                guard haveHeader, fields.count >= 3 else { return }
                switch fields[1] {
                case "datum_lat": datumLat = Double(fields[2])
                case "datum_lon": datumLon = Double(fields[2])
                default: break
                }

            case "100":
                // Land runway: end-1 lat/lon at columns 9,10 (0-indexed).
                guard haveHeader, fallbackLat == nil, fields.count >= 11,
                      let lat = Double(fields[9]), let lon = Double(fields[10]) else { return }
                fallbackLat = lat; fallbackLon = lon

            case "101":
                // Water runway: end-1 lat/lon at columns 4,5.
                guard haveHeader, fallbackLat == nil, fields.count >= 6,
                      let lat = Double(fields[4]), let lon = Double(fields[5]) else { return }
                fallbackLat = lat; fallbackLon = lon

            case "102":
                // Helipad: lat/lon at columns 2,3.
                guard haveHeader, fallbackLat == nil, fields.count >= 4,
                      let lat = Double(fields[2]), let lon = Double(fields[3]) else { return }
                fallbackLat = lat; fallbackLon = lon

            default:
                break
            }
        }

        // Chunked line reader: memory stays bounded to ~one chunk plus the
        // partial line that straddles a chunk boundary.
        let chunkSize = 1 << 20   // 1 MB
        var partial: [UInt8] = []
        while true {
            let chunk: Data
            do {
                guard let d = try handle.read(upToCount: chunkSize), !d.isEmpty else { break }
                chunk = d
            } catch { break }

            chunk.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
                let buf = raw.bindMemory(to: UInt8.self)
                var lineStart = 0
                for i in buf.indices where buf[i] == 0x0A {
                    if partial.isEmpty {
                        // Decode straight from the buffer slice — no Array copy.
                        handleLine(String(decoding: UnsafeBufferPointer(
                            rebasing: buf[lineStart..<i]), as: UTF8.self))
                    } else {
                        partial.append(contentsOf: buf[lineStart..<i])
                        handleLine(String(decoding: partial, as: UTF8.self))
                        partial.removeAll(keepingCapacity: true)
                    }
                    lineStart = i + 1
                }
                if lineStart < buf.count {
                    partial.append(contentsOf: buf[lineStart..<buf.count])
                }
            }
        }
        if !partial.isEmpty { handleLine(String(decoding: partial, as: UTF8.self)) }
        flush()   // last block runs to EOF
        return airports
    }

    // MARK: - Cache

    private struct CacheFile: Codable {
        let version: Int
        let signature: String
        let airports: [GlobalAirport]
    }

    private static let cacheVersion = 1

    /// path+size+mtime signature — a changed file rebuilds, an unchanged one
    /// loads. Both the filename key and the stored guard use it.
    private static func signature(for url: URL) -> String {
        let attrs = try? FileManager.default.attributesOfItem(atPath: url.path)
        let size = (attrs?[.size] as? NSNumber)?.doubleValue ?? -1
        let mtime = (attrs?[.modificationDate] as? Date)?.timeIntervalSince1970 ?? -1
        var hash = FNV1a()
        hash.combine(url.standardizedFileURL.path)
        hash.combine(size)
        hash.combine(mtime)
        return String(hash.value, radix: 16)
    }

    /// Load with a JSON cache: cacheDirectory/global-airports-<hash>.json
    /// keyed by the apt.dat's path+size+mtime — a changed file rebuilds,
    /// an unchanged one loads the cache. Synchronous (callers move it off
    /// the main thread); creates cacheDirectory if needed.
    public static func load(aptDatURL: URL, cacheDirectory: URL) -> [GlobalAirport] {
        let sig = signature(for: aptDatURL)
        let cacheURL = cacheDirectory
            .appendingPathComponent("global-airports-\(sig).json")

        if let data = try? Data(contentsOf: cacheURL),
           let file = try? JSONDecoder().decode(CacheFile.self, from: data),
           file.version == cacheVersion, file.signature == sig {
            return file.airports
        }

        let airports = parse(aptDatURL: aptDatURL)
        try? FileManager.default.createDirectory(
            at: cacheDirectory, withIntermediateDirectories: true)
        if let data = try? JSONEncoder().encode(
            CacheFile(version: cacheVersion, signature: sig, airports: airports)) {
            try? data.write(to: cacheURL, options: .atomic)
        }
        return airports
    }

    // MARK: - Search

    /// Ranked search: exact id match first (case-insensitive), then id
    /// prefix, then name substring; each tier alphabetical by id; at most
    /// `limit` results.
    public static func search(_ query: String, in airports: [GlobalAirport], limit: Int) -> [GlobalAirport] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty, limit > 0 else { return [] }

        var exact: [GlobalAirport] = []
        var prefix: [GlobalAirport] = []
        var nameHit: [GlobalAirport] = []
        for airport in airports {
            let idLower = airport.id.lowercased()
            if idLower == q {
                exact.append(airport)
            } else if idLower.hasPrefix(q) {
                prefix.append(airport)
            } else if airport.name.lowercased().contains(q) {
                nameHit.append(airport)
            }
        }

        let byID: (GlobalAirport, GlobalAirport) -> Bool = {
            let a = $0.id.lowercased(), b = $1.id.lowercased()
            return a == b ? $0.id < $1.id : a < b
        }
        var ranked = exact.sorted(by: byID)
        ranked += prefix.sorted(by: byID)
        ranked += nameHit.sorted(by: byID)
        return Array(ranked.prefix(limit))
    }
}
