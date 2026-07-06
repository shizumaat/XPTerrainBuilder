import Foundation
import SceneryKit

// Debug/CI harness: run the same analysis the app runs, from the terminal.
//   swift run xpdoctor-cli "/path/to/X-Plane 12" [--json] [--scope "Pack Name"]...

let args = CommandLine.arguments.dropFirst()
guard let pathArg = args.first(where: { !$0.hasPrefix("--") }) else {
    FileHandle.standardError.write(Data("usage: xpdoctor-cli <x-plane-root> [--json] [--scope <pack-name>]...\n".utf8))
    exit(2)
}
let root = URL(fileURLWithPath: pathArg, isDirectory: true)

// Debug: --query-lib <vpath> prints library index state and match results.
if let queryIndex = CommandLine.arguments.firstIndex(of: "--query-lib"),
   queryIndex + 1 < CommandLine.arguments.count {
    let vpath = CommandLine.arguments[queryIndex + 1]
    let installation = InstallationScanner(root: root).scan()
    print("installed library exports: \(installation.libraryIndex.exportCount)")
    print("default library exports: \(installation.defaultLibraryIndex.exportCount)")
    print("installed match: \(String(describing: installation.libraryIndex.caseInsensitiveMatch(for: vpath)))")
    print("default match: \(String(describing: installation.defaultLibraryIndex.caseInsensitiveMatch(for: vpath)))")
    let libs = installation.packs.filter { $0.isLibrary }
    print("library packs: \(libs.count); MisterX present: \(libs.contains { $0.name == "MisterX_Library" })")
    print("total packs: \(installation.packs.count) (installed: \(installation.packs.filter { $0.isInstalled }.count))")
    exit(0)
}

// Debug: --dsf-geometry <file.dsf> parses pools + commands and validates
// every decoded coordinate against the tile's HEAD bounds.
if let geoIndex = CommandLine.arguments.firstIndex(of: "--dsf-geometry"),
   geoIndex + 1 < CommandLine.arguments.count {
    let url = URL(fileURLWithPath: CommandLine.arguments[geoIndex + 1])
    guard let geo = DSFGeometryReader.read(url: url) else {
        print("PARSE FAILED: \(url.lastPathComponent)")
        exit(1)
    }
    let props = geo.definitions.properties
    let west = Double(props["sim/west"] ?? "") ?? -180
    let east = Double(props["sim/east"] ?? "") ?? 180
    let south = Double(props["sim/south"] ?? "") ?? -90
    let north = Double(props["sim/north"] ?? "") ?? 90
    var total = 0, inBounds = 0
    func check(_ p: GeoPoint) {
        total += 1
        if p.lon >= west - 0.001, p.lon <= east + 0.001,
           p.lat >= south - 0.001, p.lat <= north + 0.001 { inBounds += 1 }
    }
    for (_, points) in geo.objectPlacements { points.forEach(check) }
    for (_, windings) in geo.polygonWindings { windings.forEach { $0.forEach(check) } }
    let objects = geo.objectPlacements.values.reduce(0) { $0 + $1.count }
    let windings = geo.polygonWindings.values.reduce(0) { $0 + $1.count }
    print("\(url.lastPathComponent): bounds \(west)..\(east) x \(south)..\(north); " +
          "\(objects) object placements (\(geo.objectPlacements.count) defs), " +
          "\(windings) windings (\(geo.polygonWindings.count) defs); " +
          "in-bounds \(inBounds)/\(total)")
    exit(total == inBounds && total > 0 ? 0 : total == 0 ? 0 : 1)
}

// Debug: --parse-lib <pack-dir> <vpath> parses one library.txt in isolation.
if let parseIndex = CommandLine.arguments.firstIndex(of: "--parse-lib"),
   parseIndex + 2 < CommandLine.arguments.count {
    var index = LibraryIndex()
    index.indexLibrary(at: URL(fileURLWithPath: CommandLine.arguments[parseIndex + 1]), packName: "test")
    print("exports: \(index.exportCount)")
    print("match: \(String(describing: index.caseInsensitiveMatch(for: CommandLine.arguments[parseIndex + 2])))")
    exit(0)
}

// --scope <pack-name> (repeatable) limits the analysis like the app's ⌘R.
var scope: Set<String> = []
var argList = CommandLine.arguments
while let i = argList.firstIndex(of: "--scope"), i + 1 < argList.count {
    scope.insert(argList[i + 1])
    argList.removeSubrange(i...(i + 1))
}

// --cache <path> exercises the persisted per-pack cache (the app always
// caches; the CLI defaults to a fresh run for honest validation).
var options = Analyzer.Options(scope: scope.isEmpty ? nil : scope)
if let i = argList.firstIndex(of: "--cache"), i + 1 < argList.count {
    options.cacheURL = URL(fileURLWithPath: argList[i + 1])
}

let report = Analyzer(root: root).run(options: options) { event in
    if case .stage(let stage) = event {
        FileHandle.standardError.write(Data("· \(stage.label)\n".utf8))
    }
}

if args.contains("--json") {
    let data = try report.jsonData()
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} else {
    print("Findings: \(report.findings.count) " +
          "(\(report.errorCount) errors, \(report.warningCount) warnings, \(report.infoCount) info)")
    for finding in report.findings {
        print("\n[\(finding.severity.rawValue.uppercased())] \(finding.checkID) — \(finding.title)")
        print("  \(finding.detail)")
        if let suggestion = finding.suggestion { print("  fix: \(suggestion)") }
        if let url = finding.url { print("  link: \(url.absoluteString)") }
    }
}
