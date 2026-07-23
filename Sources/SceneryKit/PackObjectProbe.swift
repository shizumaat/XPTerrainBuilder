import Foundation

/// Detects whether a scenery pack ships its own 3-D objects (.obj / .agp) —
/// the content an object reseater would move onto reprofiled ground.
/// Metadata-only walk that stops at the first hit; visits are capped so a
/// mis-tagged multi-gigabyte pack can't stall the caller.
public enum PackObjectProbe {
    public static func hasCustomObjects(at packURL: URL) -> Bool {
        guard let enumerator = FileManager.default.enumerator(
            at: packURL,
            includingPropertiesForKeys: [],
            options: [.skipsHiddenFiles]
        ) else { return false }
        var visited = 0
        for case let entry as URL in enumerator {
            visited += 1
            // Payware airports run to ~10k files (Aerosoft LEMD: 8,076);
            // the cap only guards against pathological packs.
            if visited > 40000 { return false }
            if entry.lastPathComponent == "Earth nav data" {
                enumerator.skipDescendants() // DSFs/apt.dat only — no objects
                continue
            }
            let ext = entry.pathExtension.lowercased()
            if ext == "obj" || ext == "agp" { return true }
        }
        return false
    }
}
