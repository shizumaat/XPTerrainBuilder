import Foundation

// The Fly pane's events (spec `flight-manager-and-world-20261110` §5.3).
// The names are STRING LITERALS matched against the class names in
// `Ortho4XP/src/o4_engine/events.py`; the shared fixture
// `Ortho4XP/tests/fixtures/fly_pane_cases.json` is decoded in
// `FlyPaneTests`.

/// `AircraftPosition` (#2001, capability `aircraft_position`): X-Plane's
/// aircraft once a second while `aircraft_watch` is on.
public struct O4AircraftPosition: Sendable, Equatable {
    public let lat: Double
    public let lon: Double
    public let altitudeM: Double
    public let trackDegrees: Double
    public let speedMS: Double
    public let onGround: Bool
    public let paused: Bool

    public static func parse(_ object: [String: Any]) -> O4AircraftPosition {
        func double(_ key: String) -> Double { (object[key] as? NSNumber)?.doubleValue ?? 0 }
        func bool(_ key: String) -> Bool { (object[key] as? NSNumber)?.boolValue ?? false }
        return O4AircraftPosition(
            lat: double("lat"), lon: double("lon"), altitudeM: double("alt_m"),
            trackDegrees: double("track_deg"), speedMS: double("speed_ms"),
            onGround: bool("on_ground"), paused: bool("paused"))
    }
}

/// `FlightStatus` (§5.3): the flight manager's state every 2 s and at once
/// on a change. Lane F1b emits it and adds its `O4Event` case; the Fly
/// pane is built on this decoder (lane U2).
public struct O4FlightStatus: Sendable, Equatable {
    /// One readiness row `[key, state, eta_s, detail]` (§6.2).
    public struct Item: Sendable, Equatable {
        public let key: String
        public let state: String
        public let etaSeconds: Double?
        public let detail: String

        public init(key: String, state: String, etaSeconds: Double?, detail: String) {
            self.key = key
            self.state = state
            self.etaSeconds = etaSeconds
            self.detail = detail
        }
    }

    /// One job row `[tile, role, kind, state, remaining_s, margin_s]`.
    public struct Job: Sendable, Equatable {
        public let lat: Int
        public let lon: Int
        public let role: String
        public let kind: String
        public let state: String
        public let remainingSeconds: Double?
        public let marginSeconds: Double?
    }

    public let flight: String
    public let state: String
    public let phase: String
    public let ready: Bool
    public let countdownSeconds: Double?
    public let reason: String
    public let items: [Item]
    public let jobs: [Job]
    public let routeKm: Double
    public let doneKm: Double
    public let etaSeconds: Double?
    public let reload: String
    public let divertedTo: String
    /// En-route tiles that need the internet and may be left to X-Plane's
    /// own scenery (`flight_update {waive_offline: true}`, F2).
    public var waivable: [String] = []

    public static func parse(_ json: O4JSON?) -> O4FlightStatus? {
        guard let json, let flight = json["flight"]?.stringValue else { return nil }
        let items: [Item] = (json["items"]?.arrayValue ?? []).compactMap { row in
            guard let r = row.arrayValue, r.count >= 2, let key = r[0].stringValue else { return nil }
            return Item(key: key, state: r[1].stringValue ?? "waiting",
                        etaSeconds: r.count > 2 ? r[2].doubleValue : nil,
                        detail: r.count > 3 ? (r[3].stringValue ?? "") : "")
        }
        let jobs: [Job] = (json["jobs"]?.arrayValue ?? []).compactMap { row in
            guard let r = row.arrayValue, r.count >= 4, let tile = r[0].arrayValue,
                  tile.count == 2, let lat = tile[0].intValue, let lon = tile[1].intValue
            else { return nil }
            return Job(lat: lat, lon: lon, role: r[1].stringValue ?? "",
                       kind: r[2].stringValue ?? "", state: r[3].stringValue ?? "",
                       remainingSeconds: r.count > 4 ? r[4].doubleValue : nil,
                       marginSeconds: r.count > 5 ? r[5].doubleValue : nil)
        }
        var status = O4FlightStatus(
            flight: flight, state: json["state"]?.stringValue ?? "preparing",
            phase: json["phase"]?.stringValue ?? "",
            ready: json["ready"]?.boolValue ?? false,
            countdownSeconds: json["countdown_s"]?.doubleValue,
            reason: json["reason"]?.stringValue ?? "",
            items: items, jobs: jobs,
            routeKm: json["route_km"]?.doubleValue ?? 0,
            doneKm: json["done_km"]?.doubleValue ?? 0,
            etaSeconds: json["eta_s"]?.doubleValue,
            reload: json["reload"]?.stringValue ?? "",
            divertedTo: json["diverted_to"]?.stringValue ?? "")
        status.waivable = (json["waivable"]?.arrayValue ?? []).compactMap { $0.stringValue }
        return status
    }
}

/// `FlightNotice` (§5.3, lane F2): one notice of the active flight, shown
/// as a system notification (`code`, `title`, `text`, `severity`).
public struct O4FlightNotice: Sendable, Equatable {
    public let flight: String
    public let code: String
    public let title: String
    public let text: String
    public let severity: String

    public init(flight: String, code: String, title: String, text: String, severity: String) {
        self.flight = flight
        self.code = code
        self.title = title
        self.text = text
        self.severity = severity
    }

    public static func parse(_ json: O4JSON?) -> O4FlightNotice? {
        guard let json, let code = json["code"]?.stringValue, !code.isEmpty else { return nil }
        return O4FlightNotice(flight: json["flight"]?.stringValue ?? "", code: code,
                              title: json["title"]?.stringValue ?? "",
                              text: json["text"]?.stringValue ?? "",
                              severity: json["severity"]?.stringValue ?? "info")
    }
}

extension OrthoEngineClient {
    /// Start or stop `AircraftPosition` events (once a second while on).
    public func aircraftWatch(on: Bool) {
        send(command: "aircraft_watch", arguments: ["on": on])
    }

    /// A flight command of spec §5.2 (`flight_create`, `flight_update`,
    /// `flight_end`, `flight_plan_simbrief`, ...): the reply's result, or
    /// the engine's refusal sentence (an engine without the flight
    /// manager refuses every one of them).
    public func flightCommand(_ name: String, arguments: [String: Any],
                              completion: @escaping @Sendable (Result<O4JSON?, O4FlightPlanReadError>) -> Void) {
        send(command: name, arguments: arguments) { reply in
            if reply.ok {
                completion(.success(reply.result))
            } else {
                completion(.failure(O4FlightPlanReadError(message: reply.error ?? "")))
            }
        }
    }
}
