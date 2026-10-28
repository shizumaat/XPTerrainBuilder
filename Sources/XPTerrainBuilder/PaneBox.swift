import SwiftUI

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
