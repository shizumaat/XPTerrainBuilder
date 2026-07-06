import Foundation

/// Resolves a referenced path against the filesystem while tolerating the
/// name-damage classes that break scenery in the wild:
///  - letter-case differences (case-sensitive volumes),
///  - Unicode normalization (NFC reference vs NFD on disk — standard on macOS),
///  - mojibake: non-ASCII characters mangled by archive tools ("baños" on
///    disk as "ba§os" or "baÃ±os").
///
/// ASCII characters must always match exactly — an ASCII difference is a typo,
/// not encoding damage, and guessing at typos is how a fixer loses trust.
public enum PathRepair {
    public struct Resolution {
        /// The path as it actually exists on disk.
        public let url: URL
        /// Components whose on-disk spelling differs from the reference:
        /// (actual on-disk URL of that component, the spelling the reference expects).
        public let mismatches: [(actual: URL, expectedName: String)]

        public var isExact: Bool { mismatches.isEmpty }
    }

    /// Walk `relativePath` under `root`, matching each component exactly
    /// first, then case/normalization/mojibake-insensitively. Returns nil if
    /// any component has no match — or more than one (ambiguity means no
    /// safe automatic action).
    public static func resolve(relativePath: String, under root: URL) -> Resolution? {
        let fm = FileManager.default
        var current = root
        var mismatches: [(actual: URL, expectedName: String)] = []

        let components = relativePath
            .replacingOccurrences(of: "\\", with: "/")
            .split(separator: "/")
            .map(String.init)
        guard !components.isEmpty else { return nil }

        for component in components {
            let exact = current.appendingPathComponent(component)
            if fm.fileExists(atPath: exact.path) {
                current = exact
                continue
            }
            guard let entries = try? fm.contentsOfDirectory(atPath: current.path) else { return nil }
            let candidates = entries.filter { matches(reference: component, onDisk: $0) }
            guard candidates.count == 1 else { return nil }
            let actual = current.appendingPathComponent(candidates[0])
            if candidates[0] != component {
                mismatches.append((actual: actual, expectedName: component))
            }
            current = actual
        }
        return Resolution(url: current, mismatches: mismatches)
    }

    /// True when the two names plausibly denote the same file modulo
    /// case, normalization or encoding damage.
    static func matches(reference: String, onDisk: String) -> Bool {
        let refNorm = reference.precomposedStringWithCanonicalMapping.lowercased()
        let diskNorm = onDisk.precomposedStringWithCanonicalMapping.lowercased()
        if refNorm == diskNorm { return true }
        // Mojibake: identical ASCII skeleton, with at least one damaged
        // (non-ASCII) run on either side.
        let refSkeleton = skeleton(refNorm)
        let diskSkeleton = skeleton(diskNorm)
        return refSkeleton == diskSkeleton
            && refSkeleton.contains("\u{FFFD}")
    }

    /// Lowercased NFC form with every run of non-ASCII scalars collapsed to a
    /// single placeholder: "baños" -> "ba\u{FFFD}os", "baÃ±os" -> "ba\u{FFFD}os",
    /// "ba§os" -> "ba\u{FFFD}os". ASCII survives untouched so typos never match.
    static func skeleton(_ normalized: String) -> String {
        var out = String.UnicodeScalarView()
        var inRun = false
        for scalar in normalized.unicodeScalars {
            if scalar.isASCII {
                out.append(scalar)
                inRun = false
            } else if !inRun {
                out.append("\u{FFFD}")
                inRun = true
            }
        }
        return String(out)
    }
}
