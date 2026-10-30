import SwiftUI
import AppKit

/// The Build pane's body (#1537): its boxes scroll, and under them, while a
/// run or its rows are there, the run's native list (`ActivitySections`).
/// The two sit in a standard AppKit split (`RestorableSplit`, thin divider,
/// #1625): the user drags the divider to resize the list, and NSSplitView's
/// autosave keeps its height between launches. Qt: the panel's QSplitter
/// (O4_Qt_GUI.ACTIVITY_SPLIT_KEY) does the same.
struct RunListLayout<Boxes: View>: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel
    @EnvironmentObject var controller: AnalysisController
    let boxes: Boxes

    static var minListHeight: CGFloat { 80 }
    static var minBoxesHeight: CGFloat { 120 }

    init(@ViewBuilder boxes: () -> Boxes) {
        self.boxes = boxes()
    }

    var body: some View {
        if ActivitySections.shows(building: buildModel.isBuilding, activity: activity) {
            // Hosted panes don't inherit this view's environment, so the
            // objects are re-injected per pane (as MapMainView's split does).
            RestorableSplit(orientation: .vertical, autosaveName: "BuildPane.ActivitySplit",
                            firstMin: Self.minBoxesHeight, secondMin: Self.minListHeight) {
                injected(ScrollView { boxes })
            } second: {
                injected(ActivitySections())
            }
        } else {
            ScrollView { boxes }
                .frame(maxHeight: .infinity)
        }
    }

    private func injected<V: View>(_ view: V) -> some View {
        view
            .environmentObject(controller)
            .environmentObject(controller.progress)
            .environmentObject(buildModel)
            .environmentObject(activity)
            .environmentObject(buildModel.imagery)
    }
}
