import Foundation

extension XPlaneInstall {
    /// Best-effort discovery of X-Plane installs on this Mac (#819) — the
    /// Swift twin of `O4_Qt_Wizard.detect_xplane_installs`: X-Plane's own
    /// installer breadcrumbs first, then the common locations. Only folders
    /// `problem(at:)` accepts are returned, each once, in that order.
    public static func detectInstalls(
        home: String = FileManager.default.homeDirectoryForCurrentUser.path
    ) -> [String] {
        let homeURL = URL(fileURLWithPath: home, isDirectory: true)
        var candidates: [String] = []
        let prefs = homeURL.appendingPathComponent("Library/Preferences", isDirectory: true)
        for name in ["x-plane_install_12.txt", "x-plane_install_11.txt"] {
            guard let data = try? Data(contentsOf: prefs.appendingPathComponent(name)) else {
                continue
            }
            let text = String(data: data, encoding: .utf8)
                ?? String(data: data, encoding: .isoLatin1) ?? ""
            for line in text.split(whereSeparator: \.isNewline) {
                let path = line.trimmingCharacters(in: .whitespaces)
                if !path.isEmpty { candidates.append(path) }
            }
        }
        let bases = ["/Applications", home,
                     homeURL.appendingPathComponent("Desktop").path,
                     homeURL.appendingPathComponent("Applications").path]
        for base in bases {
            for name in ["X-Plane 12", "X-Plane 11"] {
                candidates.append(URL(fileURLWithPath: base).appendingPathComponent(name).path)
            }
        }
        var seen = Set<String>()
        var found: [String] = []
        for candidate in candidates {
            let path = URL(fileURLWithPath: candidate).standardized.path
            guard seen.insert(path).inserted, problem(at: path) == nil else { continue }
            found.append(path)
        }
        return found
    }
}
