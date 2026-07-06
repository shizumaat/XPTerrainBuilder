import Foundation

/// Minimal 7z extraction via the system libarchive (dyld shared cache —
/// present on every supported macOS, loaded lazily so SceneryKit keeps no
/// link-time dependency). X-Plane accepts 7z-compressed DSFs and packs like
/// Global Forests ship every tile that way; without this they were opaque
/// ("compressed") and their packs couldn't be audited at all.
///
/// Only what DSF reading needs: stream the first archive entry's bytes up to
/// a cap. LZMA decodes sequentially, so a head read never pays for the tail.
enum SevenZip {
    private struct Lib {
        let readNew: @convention(c) () -> OpaquePointer?
        let support7z: @convention(c) (OpaquePointer?) -> Int32
        let openFilename: @convention(c) (OpaquePointer?, UnsafePointer<CChar>?, Int) -> Int32
        let nextHeader: @convention(c) (OpaquePointer?, UnsafeMutablePointer<OpaquePointer?>?) -> Int32
        let readData: @convention(c) (OpaquePointer?, UnsafeMutableRawPointer?, Int) -> Int
        let readFree: @convention(c) (OpaquePointer?) -> Int32
    }

    private static let lib: Lib? = {
        guard let handle = dlopen("/usr/lib/libarchive.2.dylib", RTLD_LAZY) else { return nil }
        func sym<T>(_ name: String, as type: T.Type) -> T? {
            dlsym(handle, name).map { unsafeBitCast($0, to: type) }
        }
        guard
            let readNew = sym("archive_read_new", as: (@convention(c) () -> OpaquePointer?).self),
            let support7z = sym("archive_read_support_format_7zip",
                                as: (@convention(c) (OpaquePointer?) -> Int32).self),
            let openFilename = sym("archive_read_open_filename",
                                   as: (@convention(c) (OpaquePointer?, UnsafePointer<CChar>?, Int) -> Int32).self),
            let nextHeader = sym("archive_read_next_header",
                                 as: (@convention(c) (OpaquePointer?, UnsafeMutablePointer<OpaquePointer?>?) -> Int32).self),
            let readData = sym("archive_read_data",
                               as: (@convention(c) (OpaquePointer?, UnsafeMutableRawPointer?, Int) -> Int).self),
            let readFree = sym("archive_read_free", as: (@convention(c) (OpaquePointer?) -> Int32).self)
        else { return nil }
        return Lib(readNew: readNew, support7z: support7z, openFilename: openFilename,
                   nextHeader: nextHeader, readData: readData, readFree: readFree)
    }()

    static var available: Bool { lib != nil }

    /// The first `maxBytes` of the first file inside a 7z archive, or nil if
    /// the archive can't be opened. Shorter data than `maxBytes` means the
    /// entry ended.
    static func readHead(of url: URL, maxBytes: Int) -> Data? {
        guard let lib, let archive = lib.readNew() else { return nil }
        defer { _ = lib.readFree(archive) }
        guard lib.support7z(archive) == 0 else { return nil }
        guard url.path.withCString({ lib.openFilename(archive, $0, 64 * 1024) }) == 0 else { return nil }

        var entry: OpaquePointer?
        guard lib.nextHeader(archive, &entry) == 0 else { return nil }

        var data = Data(capacity: min(maxBytes, 1 << 20))
        var chunk = [UInt8](repeating: 0, count: 256 * 1024)
        while data.count < maxBytes {
            let want = min(chunk.count, maxBytes - data.count)
            let got = chunk.withUnsafeMutableBytes { lib.readData(archive, $0.baseAddress, want) }
            if got == 0 { break }          // end of entry
            if got < 0 { return nil }      // decode error — don't trust partials
            data.append(contentsOf: chunk[0..<got])
        }
        return data.isEmpty ? nil : data
    }
}
