import Testing
import Foundation
@testable import SceneryKit

/// The engine's imagery source list (protocol 1.15, #1345). The fixture is
/// shared with `Ortho4XP/tests/test_imagery_menu_parity.py`: the Qt window
/// builds its menus and preview URLs from it by the same rule, so a
/// difference between the two apps fails one side or the other.
struct ImagerySourcesTests {

    private struct Fixture {
        let rows: [O4ImagerySource]
        let statuses: [String: O4ImageryStatus]
        let build: [ImageryMenu.Entry]
        let map: [ImageryMenu.Entry]
        let urls: [(code: String, z: Int, x: Int, y: Int, url: String?)]
    }

    private func fixture() throws -> Fixture {
        let url = try #require(Bundle.module.url(
            forResource: "Fixtures/Imagery/imagery_menu", withExtension: "json"))
        let object = try #require(
            try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let rows = try O4JSON.from(try #require(object["rows"])).decode([O4ImagerySource].self)
        var statuses: [String: O4ImageryStatus] = [:]
        for (code, value) in object["statuses"] as? [String: [String]] ?? [:] where value.count == 2 {
            statuses[code] = O4ImageryStatus(status: value[0], reason: value[1])
        }
        func entries(_ key: String) -> [ImageryMenu.Entry] {
            (object[key] as? [[String: Any]] ?? []).map {
                ImageryMenu.Entry(code: $0["code"] as? String ?? "",
                                  label: $0["label"] as? String ?? "",
                                  enabled: $0["enabled"] as? Bool ?? false,
                                  tooltip: $0["tooltip"] as? String ?? "",
                                  section: $0["section"] as? String ?? "")
            }
        }
        let urls = (object["urls"] as? [[String: Any]] ?? []).map {
            (code: $0["code"] as? String ?? "", z: $0["z"] as? Int ?? 0,
             x: $0["x"] as? Int ?? 0, y: $0["y"] as? Int ?? 0, url: $0["url"] as? String)
        }
        return Fixture(rows: rows, statuses: statuses, build: entries("build"),
                       map: entries("map"), urls: urls)
    }

    @Test func menusMatchTheQtRule() throws {
        let f = try fixture()
        #expect(ImageryMenu.entries(f.rows, statuses: f.statuses, forMap: false) == f.build)
        #expect(ImageryMenu.entries(f.rows, statuses: f.statuses, forMap: true) == f.map)
        // OSM is map-only; Govmap can't be previewed; Arc did not answer.
        #expect(!f.build.contains { $0.code == "OSM" })
        #expect(f.map.first { $0.code == "Govmap" }?.enabled == false)
        #expect(f.map.first { $0.code == "Arc" }?.label == "Arc (offline)")
        let sections = ImageryMenu.sections(f.map).map(\.title)
        #expect(sections.first == ImageryMenu.combinedSection)
        #expect(sections.count == Set(sections).count)
    }

    @Test func previewURLsMatchTheEngine() throws {
        let f = try fixture()
        let rows = Dictionary(uniqueKeysWithValues: f.rows.map { ($0.code, $0) })
        for c in f.urls {
            let preview = try #require(rows[c.code]?.preview)
            #expect(preview.url(z: c.z, x: c.x, y: c.y) == c.url, "\(c.code) \(c.z)/\(c.x)/\(c.y)")
        }
    }

    @Test func combinedRowCarriesItsLayers() throws {
        let f = try fixture()
        let eur = try #require(f.rows.first { $0.code == "EUR" })
        #expect(eur.combined && eur.preview == nil)
        #expect(eur.members.last?.bbox == nil)                // the global base layer
        #expect(eur.members.first { $0.code == "NL" }?.bbox?.count == 4)
    }

    @Test func statusEventDecodes() {
        let event = O4Event.parse(object: [
            "event": "ImagerySourceStatus", "code": "BI", "status": "offline",
            "reason": "No answer within 5 seconds.",
        ])
        #expect(event == .imagerySourceStatus(
            code: "BI", status: O4ImageryStatus(status: "offline",
                                                reason: "No answer within 5 seconds.")))
    }
}
