import SwiftUI
import SceneryKit

struct SettingsView: View {
    @AppStorage(PrefKeys.xplanePath) private var xplanePath: String = ""
    @AppStorage(AppearanceSetting.prefKey) private var appearanceRaw: String = AppearanceSetting.system.rawValue
    @StateObject private var showingPicker = ViewState(false)

    private var isValid: Bool {
        !xplanePath.isEmpty
            && Installation.looksLikeXPlaneRoot(URL(fileURLWithPath: xplanePath, isDirectory: true))
    }

    var body: some View {
        Form {
            Section {
                LabeledContent("X-Plane Folder") {
                    HStack {
                        Text(xplanePath.isEmpty ? "Not set" : xplanePath)
                            .lineLimit(1)
                            .truncationMode(.middle)
                            .foregroundStyle(xplanePath.isEmpty ? .secondary : .primary)
                            .help(xplanePath)
                        Button("Choose…") { showingPicker.value = true }
                    }
                }
                if !xplanePath.isEmpty {
                    LabeledContent("Status") {
                        Label(
                            isValid ? "Looks like an X-Plane installation" : "Not recognized as X-Plane",
                            systemImage: isValid ? "checkmark.circle.fill" : "exclamationmark.triangle.fill"
                        )
                        .foregroundStyle(isValid ? .green : .orange)
                    }
                }
            } footer: {
                Text("The folder that contains X-Plane.app, Custom Scenery and Log.txt.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section {
                Picker("Appearance", selection: $appearanceRaw) {
                    ForEach(AppearanceSetting.allCases, id: \.rawValue) { setting in
                        Text(setting.label).tag(setting.rawValue)
                    }
                }
                .pickerStyle(.segmented)
                .onChange(of: appearanceRaw) {
                    (AppearanceSetting(rawValue: appearanceRaw) ?? .system).apply()
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 480)
        .fixedSize(horizontal: false, vertical: true)
        .fileImporter(
            isPresented: $showingPicker.value,
            allowedContentTypes: [.folder]
        ) { result in
            if case .success(let url) = result {
                xplanePath = url.path
            }
        }
    }
}
