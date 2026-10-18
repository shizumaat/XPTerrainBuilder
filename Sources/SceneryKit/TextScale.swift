import Foundation

/// The apps' text size (issue #827): View ▸ Bigger Text / Smaller Text /
/// Actual Size, remembered between launches.
///
/// The steps and the one rule both apps follow — the macOS app and the Qt
/// window (`Ortho4XP/src/O4_Text_Scale.py`, the Python half) — twinned on
/// `Ortho4XP/tests/fixtures/text_scale_cases.json`.
///
/// A scale is one of `steps`; Bigger/Smaller move one step and stop at the
/// ends; a stored value that is not a step snaps to the nearest step, and
/// an unreadable one (absent, zero, negative) is Actual Size.
public enum TextScale {
    public static let steps: [Double] = [0.85, 1.0, 1.15, 1.3, 1.45, 1.6]
    public static let defaultValue = 1.0

    /// The UserDefaults key — the Qt prefs key's string.
    public static let prefKey = "text_scale"

    public static let biggerTitle = "Bigger Text"
    public static let smallerTitle = "Smaller Text"
    public static let actualTitle = "Actual Size"

    /// The step nearest `value`; `defaultValue` when it is not a positive
    /// number.
    public static func clamp(_ value: Double) -> Double {
        guard value > 0 else { return defaultValue }  // also rejects NaN
        return steps.min { a, b in
            let da = abs(a - value), db = abs(b - value)
            return da != db ? da < db : a < b
        } ?? defaultValue
    }

    /// One step up from `value`; the largest step stays.
    public static func bigger(_ value: Double) -> Double {
        let index = steps.firstIndex(of: clamp(value)) ?? 0
        return steps[min(index + 1, steps.count - 1)]
    }

    /// One step down from `value`; the smallest step stays.
    public static func smaller(_ value: Double) -> Double {
        let index = steps.firstIndex(of: clamp(value)) ?? 0
        return steps[max(index - 1, 0)]
    }

    /// `points` at text scale `value`, rounded to a half point.
    public static func scaled(_ points: Double, _ value: Double) -> Double {
        (points * clamp(value) * 2).rounded() / 2
    }

    /// The stored scale (absent = Actual Size).
    public static func load(_ defaults: UserDefaults = .standard) -> Double {
        clamp(defaults.double(forKey: prefKey))
    }

    /// Stores `value`, clamped to a step.
    public static func save(_ value: Double, _ defaults: UserDefaults = .standard) {
        defaults.set(clamp(value), forKey: prefKey)
    }
}
