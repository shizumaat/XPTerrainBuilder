import Foundation
import SceneryKit

/// The shared patch library (#1699 phase 2): the check when the app opens,
/// laying an entry down, and the build box's match list. The engine does
/// the work (`library_check`, `library_apply`, `library_matches`); the Qt
/// window's twin is `O4_Qt_Patch_Library.py`.
extension BuildModel {
    /// Once per launch: what the library has for the installed packs and
    /// the built tiles. Nothing is applied; a line in the console says how
    /// many airports have something, and the Library window lists them.
    func checkPatchLibraryAtLaunch() {
        guard !patchLibraryCheckedAtLaunch, patchLibraryClient() != nil else { return }
        patchLibraryCheckedAtLaunch = true
        checkPatchLibrary(force: false, announce: true)
    }

    func checkPatchLibrary(force: Bool, announce: Bool = false) {
        guard let client = patchLibraryClient(), let base = tileBaseFolder else { return }
        patchLibraryStatus = "Checking the patch library…"
        Task {
            do {
                let check = try await client.libraryCheck(workingDir: base.path, force: force)
                patchLibraryCheck = check
                patchLibraryStatus = check.configured ? "" : "The patch library is not set up in this app yet."
                if announce, check.configured, !check.rows.isEmpty {
                    console.append(Self.patchLibraryNotice(check.rows))
                }
            } catch {
                patchLibraryStatus = "\(error)"
            }
        }
    }

    /// "Patch library: 2 airports have a patch available, 1 a newer one…"
    nonisolated static func patchLibraryNotice(_ rows: [O4PatchLibraryRow]) -> String {
        let count = { (state: String) in rows.filter { $0.state == state }.count }
        var parts: [String] = []
        if count("available") > 0 { parts.append("\(count("available")) with a patch available") }
        if count("newer") > 0 { parts.append("\(count("newer")) with a newer patch") }
        if count("pack_changed") > 0 { parts.append("\(count("pack_changed")) whose pack changed") }
        if count("other") > 0 { parts.append("\(count("other")) with patches for another pack version") }
        return "Patch library: airports " + parts.joined(separator: ", ") + " — see Window ▸ Library."
    }

    /// Build / Update / Use: lay one entry down for the next build.
    func applyPatchLibraryEntry(_ entry: String) async -> String {
        guard let client = patchLibraryClient(), let base = tileBaseFolder else {
            return "The engine is not running."
        }
        do {
            let done = try await client.libraryApply(entry: entry, workingDir: base.path)
            checkPatchLibrary(force: false)
            var text = done.mode == "solved"
                ? "\(done.icao) v\(done.version) laid down: the next build of \(done.tile) skips its solve."
                : "\(done.icao) will be solved here (\(done.reason))."
            if let conflict = done.conflict { text += " " + conflict.prefix(1).uppercased() + conflict.dropFirst() + "." }
            if !done.warning.isEmpty { text += " " + done.warning }
            return text
        } catch {
            return "\(error)"
        }
    }

    func ignorePatchLibraryRow(_ row: O4PatchLibraryRow) async {
        guard let client = patchLibraryClient() else { return }
        try? await client.libraryIgnore(icao: row.icao, signature: row.signature, version: row.version)
        checkPatchLibrary(force: false)
    }

    /// The build box's match list for `tiles`; nil when the engine predates
    /// it or the library is not set up.
    func patchLibraryMatches(for tiles: [TileCoord]) async -> O4PatchLibraryMatches? {
        guard !tiles.isEmpty, let client = patchLibraryClient() else { return nil }
        let refs = tiles.sorted().map { O4TileRef(lat: $0.lat, lon: $0.lon) }
        let matches = try? await client.libraryMatches(tiles: refs, workingDir: tileBaseFolder?.path ?? "")
        return (matches?.configured ?? false) ? matches : nil
    }
}
