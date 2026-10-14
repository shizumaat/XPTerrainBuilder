import SwiftUI
import SceneryKit

/// The choice for a tile that failed with a cause the user can fix (#668:
/// its Custom Scenery folder is a link to a drive that is not mounted),
/// shown AS SOON AS the tile fails while the rest of the run goes on
/// (#695). One at a time: `BuildModel.linkFixes` holds the others back.
/// Twin of the Qt window's `O4_Qt_Link_Fix.link_fix_box`.
struct LinkFixAlert: ViewModifier {
    @ObservedObject var buildModel: BuildModel

    func body(content: Content) -> some View {
        let fix = buildModel.linkFixes.current
        return content.alert(fix?.title ?? "", isPresented: Binding(
            get: { buildModel.linkFixes.current != nil },
            set: { _ in }
        ), presenting: fix) { _ in
            Button(O4TileFailureCopy.removeLinkButton) {
                buildModel.answerLinkFix(remove: true)
            }
            Button(O4TileFailureCopy.removeLinkCancel, role: .cancel) {
                buildModel.answerLinkFix(remove: false)
            }
        } message: { fix in
            Text(fix.message)
        }
    }
}
