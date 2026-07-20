import Testing
import Foundation
@testable import SceneryKit

@Suite struct OrthoKitTests {

    var engineRoot: URL {
        guard let url = Bundle.module.url(forResource: "Fixtures/FakeO4Engine", withExtension: nil) else {
            fatalError("FakeO4Engine fixture missing from test bundle")
        }
        return url
    }

    // MARK: Engine discovery

    @Test func engineLocateReadsVersion() {
        let engine = OrthoEngine.locate(at: engineRoot)
        #expect(engine != nil)
        #expect(engine?.version == "9.9.9")
        // A random folder is not an engine.
        #expect(OrthoEngine.locate(at: engineRoot.appendingPathComponent("Providers")) == nil)
    }

    @Test func providerEnumeration() {
        let providers = OrthoEngine.providers(
            inProvidersDirectory: engineRoot.appendingPathComponent("Providers"))
        let codes = providers.map { $0.code }
        #expect(codes == ["BI", "EUR"])  // HID hidden (in_GUI=False), OSM excluded
        #expect(providers.first { $0.code == "EUR" }?.isCombined == true)
        #expect(providers.first { $0.code == "BI" }?.region == "Global")
    }

    @Test func tileStateScan() {
        let states = OrthoEngine.tileStates(
            inBaseFolder: engineRoot.appendingPathComponent("Tiles"))
        #expect(states.count == 2)
        let done = states.first { $0.key == "+47+011" }
        #expect(done?.hasDSF == true)
        #expect(done?.hasConfig == true)
        let started = states.first { $0.key == "-12-069" }
        #expect(started?.hasDSF == false)
        #expect(started?.hasConfig == false)
    }

    // MARK: Config values

    @Test func valueParsingByDeclaredType() {
        #expect(O4Value.parse("True", typeName: "bool") == .bool(true))
        #expect(O4Value.parse("17", typeName: "int") == .int(17))
        #expect(O4Value.parse("1.5", typeName: "float") == .double(1.5))
        #expect(O4Value.parse("BI", typeName: "str") == .string("BI"))
        // Legacy quoted strings are stripped like the engine does.
        #expect(O4Value.parse("\"BI\"", typeName: "str") == .string("BI"))
        // masks_width is declared list but written as a bare scalar.
        #expect(O4Value.parse("100", typeName: "list") == .int(100))
        let zones = O4Value.parse("[[[47.1, 11.2, 47.3, 11.4], 18, 'BI']]", typeName: "list")
        guard case .list(let outer) = zones, case .list(let zone) = outer.first else {
            Issue.record("zone_list did not parse as nested list")
            return
        }
        #expect(zone.count == 3)
        #expect(zone[1] == .int(18))
        #expect(zone[2] == .string("BI"))
    }

    @Test func valueRendering() {
        #expect(O4Value.bool(true).cfgLiteral == "True")
        #expect(O4Value.double(25000).cfgLiteral == "25000.0")
        #expect(O4Value.double(0.25).cfgLiteral == "0.25")
        let zone = O4Value.list([.list([.double(47.1), .double(11.2)]), .int(18), .string("BI")])
        #expect(zone.cfgLiteral == "[[47.1, 11.2], 18, 'BI']")
    }

    @Test func configFileRoundTrip() throws {
        var file = try OrthoConfigFile(contentsOf: engineRoot.appendingPathComponent("Ortho4XP.cfg"))
        #expect(file.rawValues["verbosity"] == "2")
        #expect(file.rawValues["custom_unknown_key"] == "keepme")

        file.set("verbosity", to: .int(3))
        file.set("brand_new_key", to: .bool(false))
        #expect(file.rawValues["verbosity"] == "3")
        // Unknown keys and comments survive editing.
        #expect(file.lines.first == "# fixture global config")
        #expect(file.rawValues["custom_unknown_key"] == "keepme")
        #expect(file.rawValues["brand_new_key"] == "False")
    }

    @Test func typedValuesUseSchema() throws {
        guard let schema = OrthoConfigSchema.bundledSnapshot() else {
            Issue.record("bundled schema snapshot missing")
            return
        }
        let file = try OrthoConfigFile(contentsOf: engineRoot.appendingPathComponent("Ortho4XP.cfg"))
        let values = file.values(schema: schema)
        #expect(values["verbosity"] == .int(2))
        #expect(values["curvature_tol"] == .double(2.5))
        #expect(values["default_website"] == .string("EUR"))
        #expect(values["custom_unknown_key"] == nil)
    }

    // MARK: Schema

    @Test func bundledSnapshotDecodes() {
        guard let schema = OrthoConfigSchema.bundledSnapshot() else {
            Issue.record("bundled schema snapshot missing")
            return
        }
        #expect(!schema.engineVersion.isEmpty)
        #expect(schema.vars["default_zl"]?.type == "int")
        #expect(schema.vars["default_zl"]?.default == .int(16))
        #expect(schema.vars["cover_airports_with_highres"]?.label == "high_zl_airports")
        for (key, _) in OrthoConfigSchema.groupOrder {
            #expect(!schema.variables(inGroup: key).isEmpty, "group \(key) empty")
        }
    }

    /// End-to-end run of the SHIPPED dump script against the fixture engine
    /// with the stock python3 — proves the O4_OSM_Utils stub path works and
    /// the emitted JSON decodes with our model.
    @Test func schemaDumpScriptRuns() throws {
        let python = URL(fileURLWithPath: "/usr/bin/python3")
        guard FileManager.default.fileExists(atPath: python.path),
              let script = OrthoBuildRunner.schemaDumpScriptURL() else { return }
        let process = Process()
        process.executableURL = python
        process.arguments = [script.path]
        process.currentDirectoryURL = engineRoot
        let out = Pipe()
        process.standardOutput = out
        process.standardError = Pipe()
        try process.run()
        let data = out.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        #expect(process.terminationStatus == 0)
        let schema = try OrthoConfigSchema.decode(from: data)
        #expect(schema.engineVersion == "9.9.9")
        #expect(schema.vars["curvature_tol"]?.default == .double(2.0))
        #expect(schema.vars["verbosity"]?.values == ["0", "1", "2", "3"])
        #expect(schema.groups["dsf"] == ["default_website", "default_zl", "zone_list"])
    }

    // MARK: Driver protocol

    @Test func buildEventParsing() {
        #expect(OrthoBuildEvent.parse(line: "@@O4|engine|1.40.13") == .engineVersion("1.40.13"))
        #expect(OrthoBuildEvent.parse(line: "@@O4|progress|2|57") == .progress(bar: 2, percent: 57))
        #expect(OrthoBuildEvent.parse(line: "@@O4|progress|1|101") == .progress(bar: 1, percent: 100))
        #expect(OrthoBuildEvent.parse(line: "@@O4|step|mesh|start") == .stepStarted("mesh"))
        #expect(OrthoBuildEvent.parse(line: "@@O4|step|dsf|ok") == .stepFinished("dsf", ok: true))
        #expect(OrthoBuildEvent.parse(line: "@@O4|step|vector|fail") == .stepFinished("vector", ok: false))
        #expect(OrthoBuildEvent.parse(line: "@@O4|exit|ok") == .exit(.ok))
        #expect(OrthoBuildEvent.parse(line: "@@O4|exit|stopped") == .exit(.stopped))
        #expect(OrthoBuildEvent.parse(line: "@@O4|stopping") == .stopping)
        #expect(OrthoBuildEvent.parse(line: "@@O4|fatal|engine import failed") == .fatal("engine import failed"))
        #expect(OrthoBuildEvent.parse(line: "Step 2 : Building mesh...") == .console("Step 2 : Building mesh..."))
        // Malformed marker lines degrade to console output, never crash.
        #expect(OrthoBuildEvent.parse(line: "@@O4|progress|x|y") == .console("@@O4|progress|x|y"))
    }

    @Test func buildJobEncodesDriverKeys() throws {
        let job = OrthoBuildJob(lat: 47, lon: 11, steps: ["vector", "mesh"],
                                provider: "BI", zl: 17, buildDir: "",
                                tileOverrides: ["curvature_tol": .double(1.0)],
                                appOverrides: ["verbosity": .int(2)])
        let data = try JSONEncoder().encode(job)
        let object = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(object["lat"] as? Int == 47)
        #expect(object["build_dir"] as? String == "")
        let tileOverrides = try #require(object["tile_overrides"] as? [String: Any])
        #expect(tileOverrides["curvature_tol"] as? Double == 1.0)
        let appOverrides = try #require(object["app_overrides"] as? [String: Any])
        #expect(appOverrides["verbosity"] as? Int == 2)
    }

    @Test func driverScriptShipsInBundle() {
        #expect(OrthoBuildRunner.driverScriptURL() != nil)
        #expect(OrthoBuildRunner.schemaDumpScriptURL() != nil)
    }

    @Test func tileFolderNaming() {
        #expect(OrthoEngine.tileFolderName(lat: 47, lon: 11) == "zOrtho4XP_+47+011")
        #expect(OrthoEngine.tileFolderName(lat: -12, lon: -69) == "zOrtho4XP_-12-069")
    }
}
