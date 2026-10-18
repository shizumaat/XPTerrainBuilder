import SwiftUI
import SceneryKit

/// The app's text size in SwiftUI (#827). macOS has no Dynamic Type, so
/// the scale (SceneryKit `TextScale`, stored under `TextScale.prefKey`)
/// travels as an environment value set once at the window root
/// (`textScaleRoot`), and text sized by a semantic style reads it through
/// `scaledFont` — the same style at Actual Size, its macOS point size
/// times the scale otherwise.
private struct TextScaleEnvironmentKey: EnvironmentKey {
    static let defaultValue = TextScale.defaultValue
}

extension EnvironmentValues {
    var textScale: Double {
        get { self[TextScaleEnvironmentKey.self] }
        set { self[TextScaleEnvironmentKey.self] = newValue }
    }
}

extension Font.TextStyle {
    /// The style's macOS point size at Actual Size.
    var macPointSize: Double {
        switch self {
        case .largeTitle: return 26
        case .title: return 22
        case .title2: return 17
        case .title3: return 15
        case .headline, .body: return 13
        case .callout: return 12
        case .subheadline: return 11
        case .footnote, .caption, .caption2: return 10
        @unknown default: return 13
        }
    }

    /// The style's own weight (macOS headline is bold).
    var macWeight: Font.Weight { self == .headline ? .bold : .regular }
}

/// `style` at the environment's text scale.
struct ScaledFont: ViewModifier {
    @Environment(\.textScale) private var scale
    let style: Font.TextStyle
    var weight: Font.Weight?
    var design: Font.Design?
    var monospacedDigit = false

    func body(content: Content) -> some View {
        var font: Font = scale == TextScale.defaultValue
            ? .system(style, design: design, weight: weight)
            : .system(size: CGFloat(TextScale.scaled(style.macPointSize, scale)),
                      weight: weight ?? style.macWeight, design: design)
        if monospacedDigit { font = font.monospacedDigit() }
        return content.font(font)
    }
}

/// Sets the stored text scale on a window's environment, and the default
/// font of text that names no style (macOS body, 13 pt) with it.
struct TextScaleRoot: ViewModifier {
    @AppStorage(TextScale.prefKey) private var stored = TextScale.defaultValue

    func body(content: Content) -> some View {
        let scale = TextScale.clamp(stored)
        let bodyFont: Font? = scale == TextScale.defaultValue
            ? nil
            : Font.system(size: CGFloat(TextScale.scaled(13, scale)))
        return content
            .environment(\.textScale, scale)
            .environment(\.font, bodyFont)
    }
}

extension View {
    /// `.font(style)` that follows View ▸ Bigger / Smaller Text (#827).
    func scaledFont(_ style: Font.TextStyle, weight: Font.Weight? = nil,
                    design: Font.Design? = nil, monospacedDigit: Bool = false) -> some View {
        modifier(ScaledFont(style: style, weight: weight, design: design,
                            monospacedDigit: monospacedDigit))
    }

    /// The window root's text scale (#827).
    func textScaleRoot() -> some View { modifier(TextScaleRoot()) }
}

/// View ▸ Bigger Text / Smaller Text / Actual Size (⌘+ / ⌘− / ⌘0).
struct TextScaleCommands: View {
    @AppStorage(TextScale.prefKey) private var stored = TextScale.defaultValue

    var body: some View {
        let scale = TextScale.clamp(stored)
        Button(TextScale.biggerTitle) { stored = TextScale.bigger(scale) }
            .keyboardShortcut("+", modifiers: .command)
            .disabled(scale >= TextScale.steps.last ?? scale)
        Button(TextScale.smallerTitle) { stored = TextScale.smaller(scale) }
            .keyboardShortcut("-", modifiers: .command)
            .disabled(scale <= TextScale.steps.first ?? scale)
        Button(TextScale.actualTitle) { stored = TextScale.defaultValue }
            .keyboardShortcut("0", modifiers: .command)
            .disabled(scale == TextScale.defaultValue)
    }
}
