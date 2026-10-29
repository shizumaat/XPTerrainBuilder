import SwiftUI
import AppKit

/// The Build pane's body (#1537): its boxes scroll, and under them, while a
/// run or its rows are there, the run's native list (`ActivitySections`).
/// A wide divider between the two (#1625) drags to resize the list; its
/// height is kept between launches. Qt: the panel's QSplitter
/// (O4_Qt_GUI.ACTIVITY_SPLIT_KEY) does the same.
struct RunListLayout<Boxes: View>: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel
    @EnvironmentObject var controller: AnalysisController
    @AppStorage("activityPaneHeight") private var listHeight: Double = 260
    @State private var dragStart: Double?
    let boxes: Boxes

    static var minListHeight: Double { 80 }
    static var maxListHeight: Double { 2000 }

    init(@ViewBuilder boxes: () -> Boxes) {
        self.boxes = boxes()
    }

    var body: some View {
        let shows = ActivitySections.shows(building: buildModel.isBuilding, activity: activity)
        ScrollView { boxes }
            .frame(maxHeight: .infinity)
        if shows {
            divider
            ActivitySections()
                .frame(height: listHeight)
        }
    }

    /// The drag handle: a 9 pt band with a grip, easy to see and grab.
    private var divider: some View {
        ZStack {
            Rectangle().fill(Color(nsColor: .separatorColor)).frame(height: 1)
            Capsule().fill(Color.secondary.opacity(0.5)).frame(width: 36, height: 4)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 9)
        .contentShape(Rectangle())
        .onHover { inside in
            if inside { NSCursor.resizeUpDown.push() } else { NSCursor.pop() }
        }
        .gesture(DragGesture(minimumDistance: 1)
            .onChanged { drag in
                let start = dragStart ?? listHeight
                dragStart = start
                listHeight = min(Self.maxListHeight,
                                 max(Self.minListHeight, start - drag.translation.height))
            }
            .onEnded { _ in dragStart = nil })
        .accessibilityLabel("Resize Activity")
    }
}
