import SwiftUI
import AppKit
import SceneryKit

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsTab()
                .tabItem { Label("General", systemImage: "gearshape") }
            OrthoEngineTab()
                .tabItem { Label("Ortho4XP", systemImage: "globe.europe.africa.fill") }
            OrthoConfigTab()
                .tabItem { Label("Engine Config", systemImage: "slider.horizontal.3") }
        }
        .frame(width: 560)
    }
}

// MARK: - General

private struct GeneralSettingsTab: View {
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

// MARK: - Ortho4XP engine

private struct OrthoEngineTab: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var showingPicker = ViewState(false)

    var body: some View {
        Form {
            Section {
                LabeledContent("Ortho4XP Folder") {
                    HStack {
                        Text(buildModel.enginePath.isEmpty ? "Not set" : buildModel.enginePath)
                            .lineLimit(1)
                            .truncationMode(.middle)
                            .foregroundStyle(buildModel.enginePath.isEmpty ? .secondary : .primary)
                            .help(buildModel.enginePath)
                        Button("Choose…") { showingPicker.value = true }
                    }
                }
                if !buildModel.enginePath.isEmpty {
                    LabeledContent("Status") {
                        if let engine = buildModel.engine {
                            Label("Ortho4XP \(engine.version)", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        } else {
                            Label(buildModel.engineError ?? "Not recognized",
                                  systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                        }
                    }
                }
            } footer: {
                Text("A checkout or release of the Ortho4XP engine (the folder containing Ortho4XP.py). To upgrade the engine, replace the folder — or point this at a new one — and the app picks up its options automatically. Automatic updates from GitHub are planned.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let engine = buildModel.engine {
                Section {
                    LabeledContent("Python") {
                        Text(engine.hasVenv ? "Engine venv" : "System python3")
                            .foregroundStyle(.secondary)
                    }
                    LabeledContent("Environment") {
                        environmentStatus
                    }
                    HStack {
                        Button("Run Engine Setup in Terminal…") {
                            runInstallScript(engine: engine)
                        }
                        .help("Opens Terminal running install_mac.sh — installs Homebrew packages and the engine's python environment.")
                        Button("Re-check") { buildModel.reloadEngine() }
                    }
                } footer: {
                    Text("Building needs the engine's python packages (numpy, pillow, shapely, …). The setup script creates a venv inside the engine folder; the app prefers it automatically.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section {
                    LabeledContent("Imagery Providers") {
                        Text("\(buildModel.providers.count.formatted()) available")
                            .foregroundStyle(.secondary)
                    }
                    LabeledContent("Config Schema") {
                        Text(buildModel.schema.engineVersion.isEmpty
                             ? "Bundled snapshot"
                             : "From engine \(buildModel.schema.engineVersion)")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .fixedSize(horizontal: false, vertical: true)
        .fileImporter(
            isPresented: $showingPicker.value,
            allowedContentTypes: [.folder]
        ) { result in
            if case .success(let url) = result {
                buildModel.enginePath = url.path
            }
        }
    }

    @ViewBuilder
    private var environmentStatus: some View {
        if let missing = buildModel.missingPackages {
            if missing.isEmpty {
                Label("Ready", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            } else {
                Label("Missing: \(missing.joined(separator: ", "))",
                      systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
            }
        } else {
            Text("Checking…").foregroundStyle(.secondary)
        }
    }

    private func runInstallScript(engine: OrthoEngine) {
        guard FileManager.default.fileExists(atPath: engine.installScriptURL.path) else { return }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        process.arguments = ["-a", "Terminal", engine.installScriptURL.path]
        try? process.run()
    }
}

// MARK: - Engine config editor

/// The full Ortho4XP configuration, edited in place in the engine's own
/// Ortho4XP.cfg. Rows are generated from the schema the engine reported, so
/// a newer engine's added options show up here without an app update.
private struct OrthoConfigTab: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        Group {
            if buildModel.engine == nil {
                ContentUnavailableView(
                    "No Engine Configured",
                    systemImage: "globe.europe.africa",
                    description: Text("Choose the Ortho4XP folder in the Ortho4XP tab first.")
                )
                .frame(height: 420)
            } else {
                Form {
                    ForEach(OrthoConfigSchema.groupOrder, id: \.key) { group in
                        let variables = buildModel.schema.variables(inGroup: group.key)
                        if !variables.isEmpty {
                            Section(group.title) {
                                ForEach(variables, id: \.name) { variable in
                                    ConfigRow(variable: variable)
                                }
                            }
                        }
                    }
                }
                .formStyle(.grouped)
                .frame(height: 480)
            }
        }
    }
}

/// One schema variable → the matching control: allowed-values list → picker,
/// bool → toggle, everything else → a commit-on-return text field holding
/// the cfg literal.
private struct ConfigRow: View {
    @EnvironmentObject var buildModel: BuildModel
    let variable: OrthoConfigSchema.Variable

    private var current: O4Value? { buildModel.configValue(for: variable.name) }

    var body: some View {
        row.help(variable.hint.isEmpty ? variable.name : variable.hint)
    }

    @ViewBuilder
    private var row: some View {
        if let values = variable.values, !values.isEmpty {
            Picker(variable.label, selection: Binding(
                get: { current?.cfgLiteral ?? variable.default.cfgLiteral },
                set: { raw in
                    if let value = O4Value.parse(raw, typeName: variable.type) {
                        buildModel.setConfigValue(variable.name, to: value)
                    }
                }
            )) {
                ForEach(values, id: \.self) { value in
                    Text(value).tag(value)
                }
            }
        } else if variable.type == "bool" {
            Toggle(variable.label, isOn: Binding(
                get: { current?.boolValue ?? false },
                set: { buildModel.setConfigValue(variable.name, to: .bool($0)) }
            ))
        } else {
            ConfigTextRow(
                label: variable.label,
                typeName: variable.type,
                current: current?.cfgLiteral ?? "",
                commit: { raw in
                    guard let value = O4Value.parse(raw, typeName: variable.type) else { return false }
                    buildModel.setConfigValue(variable.name, to: value)
                    return true
                })
        }
    }
}

/// Text field that commits on Return and reverts on invalid input — typing
/// "1." mustn't half-write a float into the engine's config.
private struct ConfigTextRow: View {
    let label: String
    let typeName: String
    let current: String
    let commit: (String) -> Bool

    @StateObject private var text = ViewState<String?>(nil)

    var body: some View {
        TextField(label, text: Binding(
            get: { text.value ?? current },
            set: { text.value = $0 }
        ))
        .onSubmit {
            if let edited = text.value, edited != current {
                _ = commit(edited)
            }
            // Drop the buffer either way: the field shows the stored value,
            // which an invalid edit never reached.
            text.value = nil
        }
        .font(typeName == "list" ? .body.monospaced() : .body)
    }
}
