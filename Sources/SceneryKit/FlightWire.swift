import Foundation

// The flight manager's wire (spec Ortho4XP/docs/specs/
// flight-manager-and-world-20261110.md §5.2). Command names and JSON keys
// are STRING LITERALS matched against `Ortho4XP/src/o4_engine/
// flight_commands.py`; the shared fixture
// `Ortho4XP/tests/fixtures/flight_plan_wire.json` is written from the
// Python side and decoded here (`FlightWireTests`). The plan readers live
// in the engine only (spec §14); `FlightPlan.swift` stays Build mode's
// "Select from flight plan…" reader.

/// One saved X-Plane plan from `flight_plans_list` (X-Plane's
/// `Output/FMS plans/`, newest first; owner RULINGS 2026-11-10g).
public struct O4FlightPlanFile: Sendable, Equatable {
    public let path: String
    public let name: String
    public let origin: String
    public let destination: String
    /// File modification time, Unix seconds.
    public let modifiedAt: Double

    static func parse(_ json: O4JSON) -> O4FlightPlanFile? {
        guard let path = json["path"]?.stringValue else { return nil }
        return O4FlightPlanFile(
            path: path, name: json["name"]?.stringValue ?? "",
            origin: json["origin"]?.stringValue ?? "",
            destination: json["destination"]?.stringValue ?? "",
            modifiedAt: json["modified_at"]?.doubleValue ?? 0)
    }

    /// The rows of a `flight_plans_list` result (`{"plans": [...]}`).
    public static func list(from result: O4JSON?) -> [O4FlightPlanFile] {
        (result?["plans"]?.arrayValue ?? []).compactMap(parse)
    }
}

/// A waypoint or airport of a plan read by the engine; `altitudeFeet` and
/// `secondsAfterTakeoff` are nil where the plan does not say.
public struct O4FlightPlace: Sendable, Equatable {
    public let ident: String
    public let lat: Double
    public let lon: Double
    public let altitudeFeet: Double?
    public let secondsAfterTakeoff: Double?

    static func parse(_ json: O4JSON?) -> O4FlightPlace? {
        guard let json, let lat = json["lat"]?.doubleValue,
              let lon = json["lon"]?.doubleValue else { return nil }
        return O4FlightPlace(
            ident: json["ident"]?.stringValue ?? "", lat: lat, lon: lon,
            altitudeFeet: json["alt_ft"]?.doubleValue,
            secondsAfterTakeoff: json["t_s"]?.doubleValue)
    }
}

/// A plan as `flight_plan_read` answers it (`plan_wire` in
/// `flight_commands.py`).
public struct O4FlightPlanRead: Sendable, Equatable {
    public let source: String
    public let origin: String
    public let destination: String
    public let waypoints: [O4FlightPlace]
    public let alternate: O4FlightPlace?
    public let eteSeconds: Double?
    /// Planned cruise true airspeed, m/s.
    public let cruiseMS: Double?
    public let cruiseAltitudeFeet: Double?
    public let routeKm: Double

    public static func parse(_ json: O4JSON?) -> O4FlightPlanRead? {
        guard let json, let rows = json["waypoints"]?.arrayValue else { return nil }
        return O4FlightPlanRead(
            source: json["source"]?.stringValue ?? "",
            origin: json["origin"]?.stringValue ?? "",
            destination: json["destination"]?.stringValue ?? "",
            waypoints: rows.compactMap { O4FlightPlace.parse($0) },
            alternate: O4FlightPlace.parse(json["alternate"]),
            eteSeconds: json["ete_s"]?.doubleValue,
            cruiseMS: json["cruise_ms"]?.doubleValue,
            cruiseAltitudeFeet: json["cruise_alt_ft"]?.doubleValue,
            routeKm: json["route_km"]?.doubleValue ?? 0)
    }
}

/// `flight_plan_read`'s refusal: the engine's sentence for the user.
public struct O4FlightPlanReadError: Error, Sendable, Equatable {
    public let message: String
}

extension OrthoEngineClient {
    /// X-Plane's saved FMS plans, newest first; empty on any failure (an
    /// engine without the command answers ok=false).
    public func flightPlansList(
        xplaneDir: String,
        completion: @escaping @Sendable ([O4FlightPlanFile]) -> Void
    ) {
        send(command: "flight_plans_list", arguments: ["xplane_dir": xplaneDir]) { reply in
            completion(reply.ok ? O4FlightPlanFile.list(from: reply.result) : [])
        }
    }

    /// One plan file read by the engine, or why it could not be read.
    public func flightPlanRead(
        path: String,
        completion: @escaping @Sendable (Result<O4FlightPlanRead, O4FlightPlanReadError>) -> Void
    ) {
        send(command: "flight_plan_read", arguments: ["path": path]) { reply in
            if reply.ok, let plan = O4FlightPlanRead.parse(reply.result) {
                completion(.success(plan))
            } else {
                completion(.failure(O4FlightPlanReadError(
                    message: reply.error ?? "This plan could not be read.")))
            }
        }
    }
}
