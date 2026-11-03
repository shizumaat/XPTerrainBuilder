import SwiftUI
import SceneryKit

/// A slow-step alert (#1351) at the top of the Build pane: the engine's
/// title and words verbatim, one button per answer the step supports.
/// Non-modal — the build goes on, and a refreshed event replaces the words
/// in place. Qt twin: `O4_Qt_Slow_Step.slow_step_box`.
struct SlowStepBanner: View {
    let step: O4SlowStep
    let answer: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(step.title, systemImage: "hourglass")
                .scaledFont(.headline)
            Text(step.message)
                .scaledFont(.callout)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                ForEach(step.buttons, id: \.choice) { button in
                    Button(button.label) { answer(button.choice) }
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.12),
                    in: RoundedRectangle(cornerRadius: 8))
    }
}
