import Foundation
import SceneryKit

// Debug/CI harness: run the same analysis the app runs, from the terminal.
//   swift run xpdoctor-cli "/path/to/X-Plane 12" [--json]

let args = CommandLine.arguments.dropFirst()
guard let pathArg = args.first(where: { !$0.hasPrefix("--") }) else {
    FileHandle.standardError.write(Data("usage: xpdoctor-cli <x-plane-root> [--json]\n".utf8))
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

// Debug: --parse-lib <pack-dir> <vpath> parses one library.txt in isolation.
if let parseIndex = CommandLine.arguments.firstIndex(of: "--parse-lib"),
   parseIndex + 2 < CommandLine.arguments.count {
    var index = LibraryIndex()
    index.indexLibrary(at: URL(fileURLWithPath: CommandLine.arguments[parseIndex + 1]), packName: "test")
    print("exports: \(index.exportCount)")
    print("match: \(String(describing: index.caseInsensitiveMatch(for: CommandLine.arguments[parseIndex + 2])))")
    exit(0)
}

let report = Analyzer(root: root).run { event in
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
