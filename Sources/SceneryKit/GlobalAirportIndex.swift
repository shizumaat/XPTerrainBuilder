import Foundation

/// One airport from X-Plane's default (Global Airports) database. Position
/// and identity only: the index carries ~35k rows, search matches on ICAO
/// and the map labels the mark with it, so names/city/country are not
/// parsed, cached or kept in memory.
public struct GlobalAirport: Codable, Sendable {
    public let icao: String
    public let latitude: Double
    public let longitude: Double

    public init(icao: String, latitude: Double, longitude: Double) {
        self.icao = icao
        self.latitude = latitude
        self.longitude = longitude
    }
}

/// Reader for the engine's default-airport index.
///
/// This app does NOT parse apt.dat for default airports: the engine's
/// `src/O4_Airport_Index.py` is the single implementation (a second parser
/// in a second language is a drift defect waiting to happen), reached over
/// the protocol's `airport_index` command — which builds the TSV cache off
/// its own read loop and replies with the path. All that is left here is
/// reading that cache.
///
/// Custom packs' own small apt.dats are a different job and still parsed
/// natively by `InstallationScanner.parseAirports`.
public enum GlobalAirportIndex {
    /// The cache's file name inside the data folder.
    ///
    /// WIRE CONSTANT — twin of `O4_File_Names.airport_index_cache()`'s
    /// basename. It is used only for the OPTIMISTIC pre-session read (the
    /// engine replies with the full path otherwise); rename either side
    /// and this one silently stops finding the file, because the string
    /// never appears in the other language's source.
    public static let cacheFilename = ".airport_index.tsv"

    /// Airports from a cache written by `O4_Airport_Index.build_index`.
    ///
    /// The file is a header line (`O4AIRPORTIDX <version> <count>`), then
    /// `#SRC` provenance lines, then TAB-separated
    /// `code name city country lat lon category` rows (the trailing
    /// category column arrived in v3, so 6 and 7 columns are both
    /// accepted). Only columns 0/4/5 are read — stable since v1 — but a
    /// pre-v3 cache is rejected anyway: the engine always writes the
    /// category column now, so an older file means an older engine wrote
    /// it, and the engine is about to replace it.
    ///
    /// Returns nil for a missing file or an unrecognized header; malformed
    /// rows and 0/0 placeholder positions are skipped. A few MB of TSV is
    /// a plain whole-file read (this is the file that exists precisely so
    /// nobody has to stream 380 MB).
    public static func readCache(at url: URL) -> [GlobalAirport]? {
        guard let text = TextFile.contents(of: url) else { return nil }
        let lines = TextFile.lines(text)
        guard let header = lines.first else { return nil }
        let headerFields = header.split(whereSeparator: { $0 == " " || $0 == "\t" })
        guard headerFields.count >= 3, headerFields[0] == "O4AIRPORTIDX",
              let version = Int(headerFields[1]), version >= 3,
              let count = Int(headerFields[2])
        else { return nil }

        var airports: [GlobalAirport] = []
        airports.reserveCapacity(max(0, count))
        for line in lines.dropFirst() where !line.hasPrefix("#SRC") {
            let fields = line.split(separator: "\t", omittingEmptySubsequences: false)
            guard fields.count == 6 || fields.count == 7,
                  let latitude = Double(fields[4]),
                  let longitude = Double(fields[5]),
                  // The 0/0 placeholder can't be searched or drawn.
                  latitude != 0 || longitude != 0
            else { continue }
            airports.append(GlobalAirport(icao: String(fields[0]),
                                          latitude: latitude,
                                          longitude: longitude))
        }
        return airports
    }
}
