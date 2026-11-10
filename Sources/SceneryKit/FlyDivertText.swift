import Foundation

/// The Fly pane's diversion, reload and offline words and the airport
/// search of "Divert…" (spec `flight-manager-and-world-20261110` §4.3
/// steps 7-8, §7.5 S6 (b), §11; RULINGS 2026-11-10k Q3/Q4; lane F2). The
/// Qt window's `Ortho4XP/src/O4_Fly_Divert_Text.py` holds the same words
/// and rules; `FlyPaneTests` checks them against the shared fixture
/// `Ortho4XP/tests/fixtures/fly_pane_cases.json`.
public enum FlyDivertText {
    public static let divertTitle = "Divert to"
    public static let divertSearch = "Airport code or name"
    public static let divertAlternate = "The plan's alternate"
    public static let divertButton = "Divert"
    public static let reloadNow = "Reload scenery now"
    public static let notNow = "Not now"
    public static let waiveOffline = "Fly with X-Plane's own scenery there"
    /// Rows the airport search shows at most.
    public static let searchLimit = 12

    /// One airport of the search: code, name, position.
    public struct Airport: Sendable, Equatable {
        public let ident: String
        public let name: String
        public let lat: Double
        public let lon: Double

        public init(ident: String, name: String, lat: Double, lon: Double) {
            self.ident = ident
            self.name = name
            self.lat = lat
            self.lon = lon
        }
    }

    /// The exact code first, then codes starting with the query, then
    /// names containing it, each group by code; at most `limit`.
    public static func matches(_ query: String, in airports: [Airport],
                               limit: Int = searchLimit) -> [Airport] {
        let q = query.trimmingCharacters(in: .whitespaces).uppercased()
        guard !q.isEmpty else { return [] }
        var exact: [Airport] = [], prefix: [Airport] = [], named: [Airport] = []
        for airport in airports {
            let ident = airport.ident.uppercased()
            if ident == q {
                exact.append(airport)
            } else if ident.hasPrefix(q) {
                prefix.append(airport)
            } else if airport.name.uppercased().contains(q) {
                named.append(airport)
            }
        }
        func byCode(_ list: [Airport]) -> [Airport] {
            list.enumerated().sorted {
                let a = $0.element.ident.uppercased(), b = $1.element.ident.uppercased()
                return a == b ? $0.offset < $1.offset : a < b
            }.map(\.element)
        }
        return Array((byCode(exact) + byCode(prefix) + byCode(named)).prefix(max(0, limit)))
    }

    /// "CYQX · Gander International", or the code alone.
    public static func rowLabel(_ airport: Airport) -> String {
        let name = airport.name.trimmingCharacters(in: .whitespaces)
        let ident = airport.ident.uppercased()
        return name.isEmpty ? ident : "\(ident) · \(name)"
    }

    /// The reload in the air (S6 (b)), one line; empty when none waits.
    public static func reloadLine(_ status: O4FlightStatus?) -> String {
        guard let status else { return "" }
        let place = status.divertedTo.isEmpty ? "the destination" : status.divertedTo
        switch status.reload {
        case "scheduled": return "Scenery for \(place) reloads in 30 s."
        case "offered": return "Scenery for \(place) is ready: reload when you choose."
        default: return ""
        }
    }

    /// The offline waiver's line (Q3); empty when nothing can be waived.
    public static func waiverLine(_ status: O4FlightStatus?) -> String {
        let count = status?.waivable.count ?? 0
        return count == 0 ? "" : "\(count) tile(s) en route need the internet."
    }
}
