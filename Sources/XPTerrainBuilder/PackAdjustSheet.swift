import SceneryKit
import SwiftUI

/// The package adjustments question (#1916; the Qt window's
/// `O4_Qt_Pack_Adjust.PackAdjustBox`, same copy): one checkbox per
/// adjustment the engine offers, every one checked when it opens, each
/// with its explanation; the automatic rows (the flatten flag) listed
/// without a checkbox. Apply sends the checked rows and every row shown.
struct PackAdjustSheet: View {
    let adjust: O4PackAdjust
    /// `(action, items)`: "update" with the checked rows, "never", or nil
    /// (Not now).
    let answer: (String?, [String]) -> Void
    @State private var checked: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(adjust.titleText).font(.headline)
            Text(O4PackAdjustCopy.body).fixedSize(horizontal: false, vertical: true)
            ForEach(adjust.choices) { item in
                row(item) {
                    Toggle(item.title, isOn: Binding(
                        get: { checked.contains(item.key) },
                        set: { on in
                            if on { checked.insert(item.key) } else { checked.remove(item.key) }
                        }))
                }
            }
            ForEach(adjust.automatic) { item in
                row(item) {
                    Label(item.title, systemImage: "checkmark")
                }
            }
            Text(O4PackAdjustCopy.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button(O4PackAdjustCopy.neverButton) { answer("never", []) }
                Spacer()
                Button(O4PackAdjustCopy.notNowButton, role: .cancel) { answer(nil, []) }
                    .keyboardShortcut(.cancelAction)
                Button(O4PackAdjustCopy.applyButton) {
                    answer("update", adjust.choices.map(\.key).filter(checked.contains))
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onAppear { checked = Set(adjust.choices.map(\.key)) }
    }

    private func row<Title: View>(_ item: O4PackAdjustItem,
                                  @ViewBuilder title: () -> Title) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            title()
            Text(item.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .padding(.leading, 20)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// The package adjustments question on the map window (#1916). A modifier
/// of its own so `MapMainView.body` stays within the compiler's
/// type-check budget.
struct PackAdjustPrompt: ViewModifier {
    @ObservedObject var buildModel: BuildModel

    func body(content: Content) -> some View {
        content
            .sheet(item: Binding(
                get: { buildModel.packAdjustPrompt },
                set: { _ in }
            )) { adjust in
                PackAdjustSheet(adjust: adjust) { action, items in
                    buildModel.answerPackAdjustPrompt(action: action, items: items)
                }
            }
    }
}
