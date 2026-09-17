import Foundation

/// What makes a folder a USABLE X-Plane installation for a build, and why a
/// build cannot start without one (beta plan §1 B2).
///
/// The Swift twin of `O4_Settings_Model.xplane_install_problem` /
/// `resolve_cifp_dir` / `cifp_refusal_reason`. Both UIs and the engine
/// validate the same two subfolders, and the engine refuses a tile build
/// outright when auto-patch is on and no CIFP corpus resolves — so the app
/// must not offer a Build the engine will reject.
public enum XPlaneInstall {
    /// `Custom Scenery` is where a finished tile installs; `Resources/default
    /// data/CIFP` is X-Plane's own stock AIRAC corpus, and it is what makes
    /// auto-patching possible without a Navigraph subscription.
    public static let requiredSubpaths = ["Custom Scenery", "Resources/default data/CIFP"]

    /// `nil` when `path` is a usable X-Plane install, else user-facing copy
    /// saying why not.
    public static func problem(at path: String) -> String? {
        let trimmed = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "No X-Plane folder set." }
        let fm = FileManager.default
        var isDirectory: ObjCBool = false
        guard fm.fileExists(atPath: trimmed, isDirectory: &isDirectory), isDirectory.boolValue else {
            return "\(trimmed) is not a folder."
        }
        let root = URL(fileURLWithPath: trimmed, isDirectory: true)
        let missing = requiredSubpaths.filter { sub in
            var subIsDirectory: ObjCBool = false
            let exists = fm.fileExists(
                atPath: root.appendingPathComponent(sub).path, isDirectory: &subIsDirectory)
            return !(exists && subIsDirectory.boolValue)
        }
        guard missing.isEmpty else {
            return "This folder has no "
                + missing.map { "\($0)/" }.joined(separator: " and no ")
                + " — is it really an X-Plane install?"
        }
        return nil
    }

    /// The CIFP directory a tile build will ACTUALLY read, or `nil`.
    ///
    /// A non-empty `cifpDataPath` is authoritative — a typo resolves to
    /// nothing rather than silently falling back to some other corpus. An
    /// EMPTY one autodetects under the X-Plane root above
    /// `customSceneryDir`, Navigraph's `Custom Data/CIFP` winning over the
    /// stock `Resources/default data/CIFP`.
    public static func resolveCIFPDir(cifpDataPath: String, customSceneryDir: String) -> String? {
        let fm = FileManager.default
        func directory(_ path: String) -> String? {
            var isDirectory: ObjCBool = false
            guard fm.fileExists(atPath: path, isDirectory: &isDirectory), isDirectory.boolValue
            else { return nil }
            return path
        }
        let cifp = cifpDataPath.trimmingCharacters(in: .whitespacesAndNewlines)
        if !cifp.isEmpty { return directory(cifp) }
        let scenery = customSceneryDir.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !scenery.isEmpty else { return nil }
        let root = URL(fileURLWithPath: scenery, isDirectory: true).deletingLastPathComponent()
        for candidate in ["Custom Data/CIFP", "Resources/default data/CIFP"] {
            if let hit = directory(root.appendingPathComponent(candidate).path) { return hit }
        }
        return nil
    }

    /// Why the Build button must stay off, or `nil` when a build may start.
    ///
    /// The gate is the ENGINE's law, not a folder-shaped ritual: a user who
    /// pointed `cifp_data_path` straight at a Navigraph corpus is NOT
    /// blocked, because the engine can build that.
    public static func buildBlockReason(
        xplanePath: String, cifpDataPath: String, customSceneryDir: String
    ) -> String? {
        if resolveCIFPDir(cifpDataPath: cifpDataPath, customSceneryDir: customSceneryDir) != nil {
            return nil
        }
        let detail = problem(at: xplanePath) ?? "Your X-Plane folder has no CIFP data."
        return detail + " Without it every runway, taxiway and apron would drape "
            + "over the raw terrain, so the engine refuses the build. "
            + "Choose your X-Plane folder to continue."
    }
}
