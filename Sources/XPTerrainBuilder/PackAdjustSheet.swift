import SceneryKit
import SwiftUI

/// The package adjustments question (#1916; the Qt window's
/// `O4_Qt_Pack_Adjust.PackAdjustBox`, same copy): one checkbox per
/// adjustment the engine offers, ticked when it opens as the row's
/// `checked` says (the large ground textures are not, #1962), each with
/// its explanation; the automatic rows (the flatten flag) listed
/// without a checkbox. Apply sends the checked rows and every row shown.
/// The pack row's Adjust… (`adjust.editing`, owner 2026-11-15T13:12Z): the
/// rows ticked as the pack is, the Optimise steps under their heading, and
/// Apply / Cancel; Apply reads "Apply and rebuild tile" while a row the
/// tile's mesh reads (the terrain objects) differs from the pack.
struct PackAdjustSheet: View {
    let adjust: O4PackAdjust
    /// `(action, items, steps)`: "update" with the checked rows, "change"
    /// with the checked rows and steps, "never", or nil (Not now, Cancel).
    let answer: (String?, [String], [String]?) -> Void
    @State private var checked: Set<String> = []
    @State private var stepsChecked: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(adjust.titleText).font(.headline)
            Text(adjust.editing ? O4PackAdjustCopy.editBody : O4PackAdjustCopy.body)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(adjust.choices) { item in
                row(item.detail) {
                    Toggle(item.title, isOn: toggle(item.key, in: $checked))
                }
            }
            ForEach(adjust.automatic) { item in
                row(item.detail) {
                    Label(item.title, systemImage: "checkmark")
                }
            }
            if adjust.editing && !adjust.steps.isEmpty {
                Text(O4PackAdjustCopy.optimiseHeading)
                ForEach(adjust.steps) { step in
                    row(step.detail) {
                        Toggle(step.title, isOn: toggle(step.key, in: $stepsChecked))
                    }
                }
            }
            Text(O4PackAdjustCopy.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                if !adjust.editing {
                    Button(O4PackAdjustCopy.neverButton) { answer("never", [], nil) }
                }
                Spacer()
                Button(adjust.editing ? O4PackAdjustCopy.cancelButton : O4PackAdjustCopy.notNowButton,
                       role: .cancel) { answer(nil, [], nil) }
                    .keyboardShortcut(.cancelAction)
                Button(rebuilds ? O4PackAdjustCopy.applyRebuildButton : O4PackAdjustCopy.applyButton) {
                    let items = adjust.choices.map(\.key).filter(checked.contains)
                    if adjust.editing {
                        answer("change", items, adjust.steps.map(\.key).filter(stepsChecked.contains))
                    } else {
                        answer("update", items, nil)
                    }
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onAppear {
            checked = Set(adjust.choices.filter(\.checked).map(\.key))
            stepsChecked = Set(adjust.stepsOn)
        }
    }

    /// A row the tile's mesh reads is ticked otherwise than the pack is.
    private var rebuilds: Bool {
        adjust.choices.contains { item in
            item.rebuild && checked.contains(item.key) != item.baseline(editing: adjust.editing)
        }
    }

    private func toggle(_ key: String, in set: Binding<Set<String>>) -> Binding<Bool> {
        Binding(get: { set.wrappedValue.contains(key) },
                set: { on in
                    if on { set.wrappedValue.insert(key) } else { set.wrappedValue.remove(key) }
                })
    }

    private func row<Title: View>(_ detail: String,
                                  @ViewBuilder title: () -> Title) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            title()
            Text(detail)
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
                PackAdjustSheet(adjust: adjust) { action, items, steps in
                    buildModel.answerPackAdjustPrompt(action: action, items: items,
                                                      steps: steps)
                }
            }
    }
}
