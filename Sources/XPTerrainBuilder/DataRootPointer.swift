import Foundation

/// The data folder pointer both apps read (#1266): `~/.ortho4xp/data_root.txt`,
/// the file the Qt app's launcher resolves (`O4_File_Names.read_data_root_pointer`).
/// The Mac app keeps its choice in UserDefaults; mirroring it here is what lets
/// the Qt app open the same folder and see the tiles and patches built here.
enum DataRootPointer {
    static var fileURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".ortho4xp/data_root.txt")
    }

    /// Records `path` (no-op when empty or already recorded).
    static func write(_ path: String) {
        guard !path.isEmpty else { return }
        let url = fileURL
        let line = URL(fileURLWithPath: path).standardizedFileURL.path + "\n"
        if (try? String(contentsOf: url, encoding: .utf8)) == line { return }
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? line.write(to: url, atomically: true, encoding: .utf8)
    }
}
