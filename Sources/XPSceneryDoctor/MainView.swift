import SwiftUI
import SceneryKit

struct MainView: View {
    @EnvironmentObject var controller: AnalysisController
    @Environment(\.openWindow) private var openWindow
    @StateObject private var showingPicker = ViewState(false)

    static let systemInfo = SystemInfo.current()

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "stethoscope")
                .font(.system(size: 40))
                .foregroundStyle(.tint)
                .padding(.top, 8)

            Text("XPScenery Doctor")
                .font(.title2.weight(.semibold))

            pathStatus

            if controller.isRunning {
                VStack(spacing: 6) {
                    ProgressView()
                        .controlSize(.small)
                    Text(controller.stageLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                .frame(height: 44)
            } else {
                Button {
                    controller.analyze()
                } label: {
                    Label("Analyze", systemImage: "waveform.path.ecg")
                        .frame(minWidth: 120)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!controller.pathIsValid)
                .frame(height: 44)
            }

            if let report = controller.report, !controller.isRunning {
                Button("Show Report (\(report.findings.count) findings)") {
                    openWindow(id: "report")
                }
                .buttonStyle(.link)
                .font(.caption)
            }

            Text(Self.systemInfo.summary)
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .help("Performance warnings are judged against this hardware")
        }
        .padding(20)
        .frame(width: 340)
        .fixedSize()
        .onChange(of: controller.reportGeneration) {
            openWindow(id: "report")
        }
        .fileImporter(
            isPresented: $showingPicker.value,
            allowedContentTypes: [.folder]
        ) { result in
            if case .success(let url) = result {
                controller.xplanePath = url.path
            }
        }
        .alert("Error", isPresented: .constant(controller.errorMessage != nil)) {
            Button("OK") { controller.errorMessage = nil }
        } message: {
            Text(controller.errorMessage ?? "")
        }
    }

    @ViewBuilder
    private var pathStatus: some View {
        if controller.xplanePath.isEmpty {
            VStack(spacing: 8) {
                Text("Select your X-Plane folder to get started.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Button("Choose X-Plane Folder…") { showingPicker.value = true }
            }
        } else {
            HStack(spacing: 6) {
                Image(systemName: controller.pathIsValid ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .foregroundStyle(controller.pathIsValid ? .green : .orange)
                Text(controller.xplanePath)
                    .font(.caption)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .help(controller.xplanePath)
                Button {
                    showingPicker.value = true
                } label: {
                    Image(systemName: "folder")
                }
                .buttonStyle(.borderless)
                .help("Change X-Plane folder (also in Settings)")
            }
            .frame(maxWidth: 280)

            if !controller.pathIsValid {
                Text("This folder doesn't look like an X-Plane installation (no Custom Scenery or Log.txt).")
                    .font(.caption2)
                    .foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
            }
        }
    }
}
