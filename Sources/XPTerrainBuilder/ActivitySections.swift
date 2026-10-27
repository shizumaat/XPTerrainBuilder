import SwiftUI
import SceneryKit

/// The Build pane's group box: its content stacked under a label.
struct PaneBox<Content: View, Label: View>: View {
    let content: Content
    let label: Label

    init(@ViewBuilder content: () -> Content, @ViewBuilder label: () -> Label) {
        self.content = content()
        self.label = label()
    }

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                content
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(4)
        } label: {
            label
        }
    }
}

/// The Build pane's two run sections (#1556): Activity — live, failed and
/// stopped rows and the run clock — then Completed, the built tiles.
/// Completed is collapsed to its count ("Completed (12)") until its
/// disclosure opens it onto the compact rows (#1542); the choice holds for
/// the session (`BuildActivityModel.completedExpanded`). A completed tile
/// queued again moves back to Activity. Qt twin: `O4_Qt_Completed`.
struct ActivitySections: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel

    static func completedTitle(_ count: Int) -> String { "Completed (\(count))" }

    var body: some View {
        if buildModel.isBuilding || !activity.rows(in: .activity).isEmpty {
            PaneBox {
                ActivityBox(section: .activity)
            } label: {
                Text("Activity").scaledFont(.callout, weight: .semibold)
            }
        }
        let completed = activity.rows(in: .completed).count
        if completed > 0 {
            PaneBox {
                DisclosureGroup(isExpanded: $activity.completedExpanded) {
                    ActivityBox(section: .completed)
                        .padding(.top, 6)
                } label: {
                    Text(Self.completedTitle(completed))
                        .scaledFont(.callout, weight: .semibold)
                }
            } label: {
                EmptyView()
            }
        }
    }
}
