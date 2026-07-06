import Foundation

/// Central place for reading scenery text files.
///
/// X-Plane's text files (Log.txt, apt.dat, library.txt, .obj) are nominally
/// UTF-8 but frequently contain Latin-1 airport names, plugin garbage bytes,
/// or CRLF line endings. `String(contentsOf:encoding:)` throws on a single
/// bad byte, which earlier turned into a bogus "file not found" diagnosis —
/// so all reads here decode lossily (invalid bytes become U+FFFD) and can
/// only fail on real I/O errors, which callers can surface to the user.
public enum TextFile {
    public enum ReadResult {
        case ok(String)
        case notFound
        case unreadable(String)   // underlying error description (permissions, I/O)
        case tooLarge(Int)
    }

    public static func read(_ url: URL, maxBytes: Int = 256 * 1024 * 1024) -> ReadResult {
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.path) else { return .notFound }
        if let size = (try? fm.attributesOfItem(atPath: url.path))?[.size] as? Int,
           size > maxBytes {
            return .tooLarge(size)
        }
        do {
            let data = try Data(contentsOf: url, options: .mappedIfSafe)
            return .ok(String(decoding: data, as: UTF8.self))
        } catch {
            return .unreadable(error.localizedDescription)
        }
    }

    /// Convenience for callers that only care about success.
    public static func contents(of url: URL, maxBytes: Int = 256 * 1024 * 1024) -> String? {
        if case .ok(let text) = read(url, maxBytes: maxBytes) { return text }
        return nil
    }

    /// Split into lines across ALL newline conventions. In Swift, "\r\n" is
    /// a single grapheme cluster, so `split(separator: "\n")` does NOT split
    /// CRLF text — a Windows-authored library.txt parses as one giant line
    /// and silently yields nothing. Every line-parse in the engine must go
    /// through here.
    public static func lines(_ text: String) -> [Substring] {
        text.split(omittingEmptySubsequences: true) { $0 == "\n" || $0 == "\r\n" || $0 == "\r" }
    }

    /// Just the first `maxBytes` of the file, decoded lossily. For directives
    /// that live in a file's header (e.g. TEXTURE lines in OBJ8) — reading a
    /// 60 MB object in full to find them is what turns an install-wide scan
    /// into minutes.
    public static func head(of url: URL, maxBytes: Int) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        guard let data = try? handle.read(upToCount: maxBytes) else { return nil }
        return String(decoding: data, as: UTF8.self)
    }
}
