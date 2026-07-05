import Foundation

/// Well-known freeware scenery libraries, keyed by the top-level virtual path
/// prefix that appears in resource references. Used to point the user at a
/// download page when a missing library is not installed.
public enum KnownLibraries {
    public struct Entry: Sendable {
        public let name: String
        public let url: URL
    }

    /// Lowercased prefix -> library info.
    public static let byPrefix: [String: Entry] = {
        func e(_ name: String, _ url: String) -> Entry {
            Entry(name: name, url: URL(string: url)!)
        }
        return [
            "opensceneryx": e("OpenSceneryX", "https://www.opensceneryx.com/"),
            "misterx_library": e("MisterX Library", "https://forums.x-plane.org/index.php?/files/file/28167-misterx-library-and-static-aircraft-extension/"),
            "sam": e("SAM Suite / Library", "https://forums.x-plane.org/index.php?/files/file/85137-sam-suite/"),
            "sam_library": e("SAM Library", "https://forums.x-plane.org/index.php?/files/file/85137-sam-suite/"),
            "zdp_library": e("ZDP Library", "https://forums.x-plane.org/index.php?/files/file/40449-zdp-library/"),
            "cdb-library": e("CDB Library", "https://forums.x-plane.org/index.php?/files/file/33093-cdb-library/"),
            "r2_library": e("R2 Library", "https://forums.x-plane.org/index.php?/files/file/24564-r2-library/"),
            "ruscenery": e("RuScenery", "https://forums.x-plane.org/index.php?/files/file/24572-ruscenery-library/"),
            "ff_library": e("FlyByFriends (ff) Library", "https://forums.x-plane.org/index.php?/files/file/26136-ff-library-extended-lod/"),
            "world-models": e("world-models", "https://forums.x-plane.org/index.php?/files/file/27882-world-models-vehicles/"),
            "3d_people_library": e("3D People Library", "https://forums.x-plane.org/index.php?/files/file/35805-3d-people-library/"),
            "handyobjects": e("The Handy Objects Library", "https://forums.x-plane.org/index.php?/files/file/24261-the-handy-objects-library/"),
            "the_handy_objects_library": e("The Handy Objects Library", "https://forums.x-plane.org/index.php?/files/file/24261-the-handy-objects-library/"),
            "flags_of_the_world": e("Flags of the World", "https://forums.x-plane.org/index.php?/files/file/26163-flags-of-the-world-library/"),
            "naps_library": e("NAPS Library", "https://forums.x-plane.org/index.php?/files/file/44673-naps-library/"),
            "pp_library": e("PP Library", "https://forums.x-plane.org/index.php?/files/file/35247-pp-library/"),
            "bs2001": e("BS2001 Object Library", "https://forums.x-plane.org/index.php?/files/file/9868-bs2001-object-library/"),
            "x-csl": e("X-CSL Package", "https://csl.x-air.ru/?lang_id=43"),
            "re_library": e("RE_Library", "https://forums.x-plane.org/index.php?/files/file/40967-re_library/"),
            "ra_library": e("RA Library", "https://forums.x-plane.org/index.php?/files/file/39434-ra-library/"),
            "graintractor": e("Grain Tractor Library", "https://forums.x-plane.org/index.php?/files/category/5-scenery-libraries/"),
            "airport_environment": e("Airport Environment HD", "https://forums.x-plane.org/index.php?/files/file/35411-airport-environment-hd/"),
        ]
    }()

    public static func lookup(prefix: String) -> Entry? {
        byPrefix[prefix.lowercased()]
    }

    /// Fallback: a search on the x-plane.org downloads section for the prefix.
    public static func searchURL(for prefix: String) -> URL {
        let query = prefix.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? prefix
        return URL(string: "https://forums.x-plane.org/index.php?/search/&q=\(query)&type=downloads_file")!
    }
}
