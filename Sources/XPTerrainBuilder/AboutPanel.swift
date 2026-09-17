import AppKit
import SceneryKit

/// The About box — the one place a beta tester can read the build triple off
/// (docs/BETA-PLAN-20260916.md §1 B3). AppKit's standard panel shows
/// `CFBundleShortVersionString` and nothing else, which names the app build
/// but not the engine build or the commit, so the triple goes in as the
/// credits body.
enum AboutPanel {
    /// `engineVersion` is the version the running engine announced in its
    /// handshake, used only when the bundle carries no stamp (a `swift run`
    /// tree). A release build always shows what make_app.sh stamped, so the
    /// About box reports the engine that SHIPPED even before one is started.
    static func show(engineVersion: String?) {
        let live = (engineVersion?.isEmpty ?? true) ? nil : engineVersion
        NSApp.orderFrontStandardAboutPanel(options: [
            .credits: credits(for: AppVersion.triple(liveEngineVersion: live)),
        ])
        NSApp.activate(ignoringOtherApps: true)
    }

    /// The credits body, as an attributed string in the panel's own font —
    /// `orderFrontStandardAboutPanel` renders `.credits` at 12 pt Times
    /// otherwise, which reads as a bug.
    static func credits(for triple: BuildTriple) -> NSAttributedString {
        let style = NSMutableParagraphStyle()
        style.alignment = .center
        style.paragraphSpacing = 2
        return NSAttributedString(
            string: triple.displayLines.joined(separator: "\n"),
            attributes: [
                .font: NSFont.systemFont(ofSize: NSFont.smallSystemFontSize),
                .foregroundColor: NSColor.secondaryLabelColor,
                .paragraphStyle: style,
            ]
        )
    }
}
