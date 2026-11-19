import SceneryKit
import SwiftUI

/// A read-only airport pack (capability pack_readonly, #2174): Make
/// writable / Not now, the Qt question's copy. Both answers are sent: the
/// build's writes of the pack wait for either.
struct PackReadOnlyPrompt: ViewModifier {
    @ObservedObject var buildModel: BuildModel

    func body(content: Content) -> some View {
        content
            .alert(buildModel.packReadOnlyPrompt?.titleText ?? "", isPresented: Binding(
                get: { buildModel.packReadOnlyPrompt != nil },
                set: { _ in }
            ), presenting: buildModel.packReadOnlyPrompt) { _ in
                Button(O4PackReadOnlyCopy.writableButton) {
                    buildModel.answerPackReadOnlyPrompt(action: "writable")
                }
                Button(O4PackReadOnlyCopy.notNowButton, role: .cancel) {
                    buildModel.answerPackReadOnlyPrompt(action: "not_now")
                }
            } message: { readOnly in
                Text(readOnly.bodyText)
            }
    }
}
