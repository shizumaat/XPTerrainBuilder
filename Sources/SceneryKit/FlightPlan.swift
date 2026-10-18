import Foundation

/// Select tiles from a flight plan (issue #829): the Swift half of ONE rule
/// whose Python half (the Qt window's) is `Ortho4XP/src/O4_Flight_Plan.py`.
/// Both read `Ortho4XP/tests/fixtures/flight_plan_cases.json` and the plan
/// files in `Ortho4XP/tests/fixtures/flight_plan/`.
///
/// This file reads plans — an X-Plane `.fms` (v3 and v11: every
/// `TYPE IDENT … LAT LON` line of a waypoint type), a Little Navmap
/// `.lnmpln` (`Flightplan/Waypoints/Waypoint/Pos @Lat @Lon`) and SimBrief's
/// fetcher XML (`origin`, `navlog/fix`, `destination`, each `pos_lat` /
/// `pos_long`). `RouteTiles` turns the route into tiles.
public struct FlightPlan: Sendable, Equatable {
    public struct Waypoint: Sendable, Equatable {
        public let ident: String
        public let lat: Double
        public let lon: Double

        public init(ident: String, lat: Double, lon: Double) {
            self.ident = ident
            self.lat = lat
            self.lon = lon
        }
    }

    public let waypoints: [Waypoint]
    /// Where the plan came from: the file name, or "SimBrief".
    public let source: String

    public var origin: String { waypoints.first?.ident ?? "" }
    public var destination: String { waypoints.last?.ident ?? "" }
    public var points: [(lat: Double, lon: Double)] { waypoints.map { ($0.lat, $0.lon) } }
}

/// A plan that cannot be read; `message` is for the user.
public struct FlightPlanError: Error, LocalizedError, Equatable {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var errorDescription: String? { message }
}

/// The dialog's words and the radius control (identical to the Python half).
public enum FlightPlanCopy {
    public static let menuTitle = "Select from flight plan\u{2026}"
    public static let openButton = "Open plan file\u{2026}"
    public static let simBriefPlaceholder = "SimBrief username or pilot ID"
    public static let simBriefButton = "Fetch latest SimBrief plan"
    public static let simBriefNote = "Downloads your latest plan from simbrief.com (needs internet)."
    public static let radiusLabel = "Tiles within"
    public static let ofRouteLabel = "of the route"
    public static let fileTypes = ["fms", "lnmpln"]
    /// km is the app's unit everywhere else; nm is the pilot's.
    public static let units = ["km", "nm"]
    public static let radiusMax = ["km": 300, "nm": 160]
    public static let radiusDefault = ["km": 50, "nm": 25]
}

public enum FlightPlanReader {
    public static let simBriefEndpoint = "https://www.simbrief.com/api/xml.fetcher.php"

    /// X-Plane .fms waypoint types: airport, NDB, VOR, fix, DME, lat/lon.
    private static let fmsTypes: Set<Int> = [1, 2, 3, 11, 12, 13, 28]

    static func plausible(_ lat: Double, _ lon: Double) -> Bool {
        lat.isFinite && lon.isFinite && (-90...90).contains(lat) && (-180...180).contains(lon)
    }

    private static func number(_ text: String?) -> Double? {
        guard let text else { return nil }
        return Double(text.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// Drop repeated consecutive positions; a route needs two points.
    static func plan(_ waypoints: [FlightPlan.Waypoint], source: String,
                     kind: String) throws -> FlightPlan {
        var kept: [FlightPlan.Waypoint] = []
        for w in waypoints {
            if let last = kept.last, last.lat == w.lat, last.lon == w.lon { continue }
            kept.append(w)
        }
        guard let first = kept.first else {
            throw FlightPlanError("No waypoints found in this \(kind).")
        }
        if kept.count == 1 { kept.append(first) }
        return FlightPlan(waypoints: kept, source: source)
    }

    public static func parseFMS(_ text: String, source: String = "") throws -> FlightPlan {
        var waypoints: [FlightPlan.Waypoint] = []
        for line in text.split(whereSeparator: \.isNewline) {
            let tokens = line.split(whereSeparator: \.isWhitespace).map(String.init)
            guard tokens.count >= 5, let kind = Int(tokens[0]),
                  let lat = Double(tokens[tokens.count - 2]),
                  let lon = Double(tokens[tokens.count - 1]),
                  fmsTypes.contains(kind), plausible(lat, lon) else { continue }
            waypoints.append(.init(ident: tokens[1], lat: lat, lon: lon))
        }
        return try plan(waypoints, source: source, kind: "X-Plane flight plan")
    }

    private static func xmlRoot(_ text: String, kind: String) throws -> XMLElement {
        guard let doc = try? XMLDocument(xmlString: text, options: [.nodeLoadExternalEntitiesNever]),
              let root = doc.rootElement() else {
            throw FlightPlanError("This \(kind) is not valid XML.")
        }
        return root
    }

    private static func child(_ node: XMLElement?, _ path: [String]) -> XMLElement? {
        var current = node
        for name in path { current = current?.elements(forName: name).first }
        return current
    }

    private static func childText(_ node: XMLElement?, _ name: String) -> String? {
        child(node, [name])?.stringValue
    }

    public static func parseLNMPLN(_ text: String, source: String = "") throws -> FlightPlan {
        let root = try xmlRoot(text, kind: "Little Navmap plan")
        let list = child(root, ["Flightplan", "Waypoints"])?.elements(forName: "Waypoint") ?? []
        var waypoints: [FlightPlan.Waypoint] = []
        for wp in list {
            guard let pos = child(wp, ["Pos"]),
                  let lat = number(pos.attribute(forName: "Lat")?.stringValue),
                  let lon = number(pos.attribute(forName: "Lon")?.stringValue),
                  plausible(lat, lon) else { continue }
            let ident = [childText(wp, "Ident"), childText(wp, "Name")]
                .compactMap { $0 }.first { !$0.isEmpty } ?? ""
            waypoints.append(.init(ident: ident.trimmingCharacters(in: .whitespacesAndNewlines),
                                   lat: lat, lon: lon))
        }
        return try plan(waypoints, source: source, kind: "Little Navmap plan")
    }

    private static func simBriefPoint(_ node: XMLElement?) -> FlightPlan.Waypoint? {
        guard let node, let lat = number(childText(node, "pos_lat")),
              let lon = number(childText(node, "pos_long")), plausible(lat, lon) else { return nil }
        let ident = [childText(node, "icao_code"), childText(node, "ident")]
            .compactMap { $0 }.first { !$0.isEmpty } ?? ""
        return .init(ident: ident.trimmingCharacters(in: .whitespacesAndNewlines), lat: lat, lon: lon)
    }

    /// SimBrief's fetcher XML. A fetch SimBrief refused carries its reason
    /// in `fetch/status`; that reason is the error message.
    public static func parseSimBrief(_ text: String, source: String = "SimBrief") throws -> FlightPlan {
        let root = try xmlRoot(text, kind: "SimBrief answer")
        let status = (child(root, ["fetch", "status"])?.stringValue ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if !status.isEmpty, status.lowercased() != "success" {
            let reason = status.replacingOccurrences(of: #"(?i)^error:\s*"#, with: "",
                                                     options: .regularExpression)
            throw FlightPlanError("SimBrief: \(reason)")
        }
        var points = [simBriefPoint(child(root, ["origin"]))]
        points += (child(root, ["navlog"])?.elements(forName: "fix") ?? []).map { simBriefPoint($0) }
        points.append(simBriefPoint(child(root, ["destination"])))
        return try plan(points.compactMap { $0 }, source: source, kind: "SimBrief plan")
    }

    /// Any of the three, chosen by the file extension, else by content.
    public static func parsePlanText(_ text: String, name: String = "") throws -> FlightPlan {
        let ext = name.contains(".") ? (name.components(separatedBy: ".").last ?? "").lowercased() : ""
        if ext == "lnmpln" { return try parseLNMPLN(text, source: name) }
        if ext == "fms" { return try parseFMS(text, source: name) }
        let head = String(text.drop(while: { $0.isWhitespace }).prefix(4096))
        if head.hasPrefix("<") {
            if head.contains("<LittleNavmap") { return try parseLNMPLN(text, source: name) }
            if head.contains("<OFP") { return try parseSimBrief(text, source: name.isEmpty ? "SimBrief" : name) }
        }
        return try parseFMS(text, source: name)
    }

    /// Read `url` (UTF-8; an unreadable byte is replaced) and parse it.
    public static func readPlanFile(_ url: URL) throws -> FlightPlan {
        let data: Data
        do {
            data = try Data(contentsOf: url)
        } catch {
            throw FlightPlanError("Could not read \(url.path) (\(error.localizedDescription)).")
        }
        return try parsePlanText(String(decoding: data, as: UTF8.self), name: url.lastPathComponent)
    }

    /// The fetcher URL for a SimBrief pilot ID (digits) or username; only
    /// A-Z a-z 0-9 - . _ ~ are left unencoded (as the Python half).
    public static func simBriefURL(_ user: String) throws -> String {
        let user = user.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !user.isEmpty else {
            throw FlightPlanError("Enter your SimBrief username or pilot ID.")
        }
        let key = user.allSatisfy({ $0.isASCII && $0.isNumber }) ? "userid" : "username"
        let bare = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        let value = user.addingPercentEncoding(withAllowedCharacters: bare) ?? user
        return "\(simBriefEndpoint)?\(key)=\(value)"
    }

    /// Download and parse the user's latest SimBrief plan (network).
    public static func fetchSimBrief(user: String) async throws -> FlightPlan {
        guard let url = URL(string: try simBriefURL(user)) else {
            throw FlightPlanError("Enter your SimBrief username or pilot ID.")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let data: Data
        do {
            // SimBrief answers an unknown user with an error status AND an
            // XML body naming the reason, so the body is read either way.
            let (body, _) = try await URLSession.shared.data(for: request)
            data = body
        } catch {
            throw FlightPlanError("Could not reach simbrief.com (\(error.localizedDescription)).")
        }
        return try parseSimBrief(String(decoding: data, as: UTF8.self))
    }
}
