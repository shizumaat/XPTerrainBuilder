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
