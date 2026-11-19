import Foundation

/// The Build pane's Airports card (protocol 1.18, #818): what airport
/// grading and object fitting will do for the tiles about to be built.
/// The engine's `o4_engine/build_airports.py` is the one reader; the Qt
/// window calls it in process, this app through `build_airports`.
public struct O4BuildAirports: Sendable, Equatable {
    /// One airport the build grades.
    public struct Airport: Sendable, Equatable, Identifiable {
        public var id: String { icao }
        public let icao: String
        /// "" when the Global Airports index has not been built.
        public let name: String
        /// "FAA" | "ICAO" — the law's own resolver, from the identifier.
        public let ruleset: String
        public let tile: O4TileRef?
        /// Seconds to grade it, low and high: a range, never one number.
        public let estimateSeconds: ClosedRange<Double>
    }

    /// One custom airport pack whose 3-D objects fitting may reseat.
    public struct Pack: Sendable, Equatable, Identifiable {
        public var id: String { path }
        public let name: String
        public let path: String
        public let airports: [String]
        public let objects: Int
    }

    /// One airport's own "Fit custom airport buildings" switch (#2182,
    /// capability `airport_fit`): kept for its later builds.
    public struct FitAirport: Sendable, Equatable, Identifiable {
        public var id: String { "\(tile.lat),\(tile.lon),\(icao)" }
        public let icao: String
        public let tile: O4TileRef
        /// What its next build does: its own value, else the tile's.
        public let fit: Bool
        public let customPatch: Bool
        /// The engine's question before it turns on; "" = none.
        public let confirm: String

        public init(icao: String, tile: O4TileRef, fit: Bool,
                    customPatch: Bool = false, confirm: String = "") {
            self.icao = icao
            self.tile = tile
            self.fit = fit
            self.customPatch = customPatch
            self.confirm = confirm
        }
    }

    public let airports: [Airport]
    public let packs: [Pack]
    public let totalSeconds: ClosedRange<Double>
    /// The airports a custom patch covers in the tiles (owner RULINGS
    /// 2026-11-18l, #2172).
    public let customPatches: [String]
    /// Whether the next build fits custom airport buildings: off on a
    /// tile a custom patch is new to; nil from an engine that predates it.
    public let fitBuildings: Bool?
    /// The engine's question before the fit switch turns on; "" = none.
    public let fitConfirm: String
    /// The switch per airport (#2182); empty from an engine that predates it.
    public let fitAirports: [FitAirport]

    public init(airports: [Airport], packs: [Pack], totalSeconds: ClosedRange<Double>,
                customPatches: [String] = [], fitBuildings: Bool? = nil,
                fitConfirm: String = "", fitAirports: [FitAirport] = []) {
        self.airports = airports
        self.packs = packs
        self.totalSeconds = totalSeconds
        self.customPatches = customPatches
        self.fitBuildings = fitBuildings
        self.fitConfirm = fitConfirm
        self.fitAirports = fitAirports
    }

    /// A `[low, high]` wire pair, ordered; nil when absent or malformed.
    static func range(_ json: O4JSON?) -> ClosedRange<Double>? {
        guard let pair = json?.arrayValue, pair.count >= 2,
              let low = pair[0].doubleValue, let high = pair[1].doubleValue
        else { return nil }
        return min(low, high)...max(low, high)
    }

    /// One `BuildAirportsReady` event → the card, or its error.
    static func decode(_ event: O4JSON?) -> Result<O4BuildAirports, Error> {
        guard let event else {
            return .failure(O4CommandError("The engine exited before the airports were read."))
        }
        if let text = event["error"]?.stringValue, !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        let airports = (event["airports"]?.arrayValue ?? []).compactMap { row -> Airport? in
            guard let icao = row["icao"]?.stringValue else { return nil }
            var tile: O4TileRef?
            if let pair = row["tile"]?.arrayValue, pair.count >= 2,
               let lat = pair[0].intValue, let lon = pair[1].intValue {
                tile = O4TileRef(lat: lat, lon: lon)
            }
            return Airport(icao: icao, name: row["name"]?.stringValue ?? "",
                           ruleset: row["ruleset"]?.stringValue ?? "",
                           tile: tile,
                           estimateSeconds: range(row["estimate_s"]) ?? 0...0)
        }
        let packs = (event["packs"]?.arrayValue ?? []).compactMap { row -> Pack? in
            guard let name = row["name"]?.stringValue else { return nil }
            return Pack(name: name, path: row["path"]?.stringValue ?? name,
                        airports: row["airports"]?.arrayValue?.compactMap(\.stringValue) ?? [],
                        objects: row["objects"]?.intValue ?? 0)
        }
        let fitAirports = (event["fit_airports"]?.arrayValue ?? []).compactMap { row -> FitAirport? in
            guard let icao = row["icao"]?.stringValue,
                  let pair = row["tile"]?.arrayValue, pair.count >= 2,
                  let lat = pair[0].intValue, let lon = pair[1].intValue else { return nil }
            return FitAirport(icao: icao, tile: O4TileRef(lat: lat, lon: lon),
                              fit: row["fit"]?.boolValue ?? false,
                              customPatch: row["custom_patch"]?.boolValue ?? false,
                              confirm: row["confirm"]?.stringValue ?? "")
        }
        return .success(O4BuildAirports(
            airports: airports, packs: packs,
            totalSeconds: range(event["total_s"]) ?? 0...0,
            customPatches: event["custom_patches"]?.arrayValue?.compactMap(\.stringValue) ?? [],
            fitBuildings: event["fit_buildings"]?.boolValue,
            fitConfirm: event["fit_confirm"]?.stringValue ?? "",
            fitAirports: fitAirports))
    }
}

extension O4ProtocolVersion {
    /// `build_airports` and the `overrides` build keyword (#818).
    public static func supportsBuildAirports(_ version: String) -> Bool {
        isAtLeast(version, 1, 18)
    }
}

/// The `set_airport_fit` reply.
struct O4SetAirportFitReply: Decodable, Sendable {
    let tile: String
    let icao: String
    let fit: Bool
}

extension OrthoEngineClient {
    /// One airport's own "Fit custom airport buildings" value in its tile
    /// (#2182, capability `airport_fit`), kept for its later builds.
    public func setAirportFit(tile: String, icao: String, fit: Bool,
                              customBuildDir: String = "") async throws {
        let _: O4SetAirportFitReply = try await request(
            "set_airport_fit", ["tile": tile, "icao": icao, "fit": fit,
                                "custom_build_dir": customBuildDir])
    }

    /// Asynchronous on the engine side: the reply is `{"status": "started"}`
    /// and the `BuildAirportsReady` event naming this command's id carries
    /// the card or the error.
    public func buildAirports(tiles: [O4TileRef], customBuildDir: String) async throws -> O4BuildAirports {
        let once = O4ResumeOnce<O4BuildAirports>()
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: "build_airports",
                 arguments: ["tiles": tiles.map { [$0.lat, $0.lon] },
                             "custom_build_dir": customBuildDir],
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused build_airports.")))
                     }
                 },
                 completionEvent: { event in once.resume(O4BuildAirports.decode(event)) })
        }
    }
}
