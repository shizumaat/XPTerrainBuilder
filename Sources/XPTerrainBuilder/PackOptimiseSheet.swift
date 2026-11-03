import SceneryKit
import SwiftUI

/// The "Optimise pack" question with its steps (#1707; the Qt window's
/// `O4_Qt_Pack_Optimise.PackOptimiseBox`, same copy): one checkbox per
/// step the engine has work for, checked as the pack's last choice was
/// (every step at first), each with its explanation and estimate.
/// Optimise sends the checked steps and is disabled with none checked.
struct PackOptimiseSheet: View {
    let optimise: O4PackOptimise
    /// `(action, steps)`: "update" with the checked steps, "never", or
    /// nil (Not now).
    let answer: (String?, [String]) -> Void
    @State private var checked: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(optimise.titleText).font(.headline)
            Text(optimise.stepsBodyText).fixedSize(horizontal: false, vertical: true)
            ForEach(optimise.steps) { step in
                VStack(alignment: .leading, spacing: 2) {
                    Toggle(step.title, isOn: Binding(
                        get: { checked.contains(step.key) },
                        set: { on in
                            if on { checked.insert(step.key) } else { checked.remove(step.key) }
                        }))
                    Text(step.detail)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .padding(.leading, 20)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Text(O4PackOptimiseCopy.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button(O4PackOptimiseCopy.neverButton) { answer("never", []) }
                Spacer()
                Button(O4PackOptimiseCopy.notNowButton, role: .cancel) { answer(nil, []) }
                    .keyboardShortcut(.cancelAction)
                Button(O4PackOptimiseCopy.optimiseButton) {
                    answer("update", optimise.steps.map(\.key).filter(checked.contains))
                }
                .keyboardShortcut(.defaultAction)
                .disabled(checked.isEmpty)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onAppear { checked = optimise.initiallyChecked }
    }
}
