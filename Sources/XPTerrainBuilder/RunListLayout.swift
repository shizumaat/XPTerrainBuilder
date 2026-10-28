import SwiftUI

/// The Build pane's body (#1537): its boxes scroll, and under them, while a
/// run or its rows are there, the run's native list (`ActivitySections`)
/// takes the rest of the pane. The boxes' scroll is never taller than the
/// boxes, so the list gets every point they do not need. Qt: the panel's
/// Activity list absorbs the free height the same way.
struct RunListLayout<Boxes: View>: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel
    @EnvironmentObject var controller: AnalysisController
    @State private var boxesHeight: CGFloat = .infinity
    let boxes: Boxes

    init(@ViewBuilder boxes: () -> Boxes) {
        self.boxes = boxes()
    }

    var body: some View {
        let shows = ActivitySections.shows(building: buildModel.isBuilding, activity: activity)
        ScrollView {
            boxes.onGeometryChange(for: CGFloat.self) { $0.size.height } action: {
                boxesHeight = $0
            }
        }
        .frame(maxHeight: shows ? boxesHeight : .infinity)
        if shows {
            Divider()
            ActivitySections()
        }
    }
}
