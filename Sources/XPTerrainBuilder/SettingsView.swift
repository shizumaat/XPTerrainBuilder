import SwiftUI
import AppKit
import SceneryKit

/// System Settings-style window: a searchable sidebar of sections. General
/// holds the app's own settings plus the Ortho4XP app-level ones (engine,
/// status, runtime); the remaining sections mirror the Qt UI's categories
/// and edit the engine config — globally, or as per-tile overrides when
/// tiles are selected on the map (the Qt "blended view" semantics).
struct SettingsView: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var selection = ViewState<String?>("general")
    @StateObject private var query = ViewState("")

    /// Overridden settings for the map selection, grouped in category order.
    /// Drives both the sidebar's "Selected Overrides" entry and its pane.
    private var overriddenByCategory: [(category: SettingCategory, items: [SettingItem])] {
        _ = buildModel.tileConfigGeneration
        guard !buildModel.selected.isEmpty else { return [] }
        let names = buildModel.overriddenNames()
        guard !names.isEmpty else { return [] }
        return SettingsLayout.categories.compactMap { category in
            let hit = category.items.filter {
                $0.scope == .tile && names.contains($0.name)
                    && buildModel.schema.vars[$0.name] != nil
            }
            return hit.isEmpty ? nil : (category, hit)
        }
    }

    var body: some View {
        let overrides = overriddenByCategory
        NavigationSplitView {
            VStack(spacing: 0) {
                searchField
                List(selection: $selection.value) {
                    Label("General", systemImage: "gearshape")
                        .tag("general")
                    if !overrides.isEmpty {
                        Label("Selected Overrides", systemImage: "square.grid.3x3.topleft.filled")
                            .tag("overrides")
                    }
                    Section("Engine") {
                        ForEach(SettingsLayout.categories) { category in
                            Label(category.title, systemImage: category.icon)
                                .tag(category.key)
                        }
                    }
                }
                .listStyle(.sidebar)
            }
            .toolbar(removing: .sidebarToggle)
            .navigationSplitViewColumnWidth(min: 210, ideal: 230, max: 280)
        } detail: {
            detail(overrides: overrides)
        }
        .frame(minWidth: 840, idealWidth: 880, minHeight: 560, idealHeight: 620)
    }

    private var searchField: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
            TextField("Search settings", text: $query.value)
                .textFieldStyle(.plain)
            if !query.value.isEmpty {
                Button {
                    query.value = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(6)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 7))
        .padding(.horizontal, 10)
        .padding(.top, 10)
    }

    @ViewBuilder
    private func detail(overrides: [(category: SettingCategory, items: [SettingItem])]) -> some View {
        if !query.value.trimmingCharacters(in: .whitespaces).isEmpty {
            SearchResultsPane(query: query.value)
        } else if selection.value == "overrides", !overrides.isEmpty {
            OverridesPane(overrides: overrides)
        } else if let key = selection.value,
                  let category = SettingsLayout.categories.first(where: { $0.key == key }) {
            CategoryPane(category: category)
        } else {
            GeneralPane()
        }
    }
}

// MARK: - Selected overrides

/// All settings the selected tiles customize, grouped by their settings
/// category, each with a revert-to-global button.
private struct OverridesPane: View {
    @EnvironmentObject var buildModel: BuildModel
    let overrides: [(category: SettingCategory, items: [SettingItem])]

    var body: some View {
        Form {
            ForEach(overrides, id: \.category.key) { group in
                Section(group.category.title) {
                    ForEach(group.items) { item in
                        ConfigItemRow(item: item, showsRevert: true)
                    }
                }
            }
            Section {
                Button("Reset All to Global") {
                    buildModel.revertTileOverrides(
                        for: overrides.flatMap { $0.items.map(\.name) })
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Selected Overrides")
    }
}

// MARK: - Search

private struct SearchResultsPane: View {
    @EnvironmentObject var buildModel: BuildModel
    let query: String

    private var matches: [(category: String, item: SettingItem)] {
        let needle = query.trimmingCharacters(in: .whitespaces).lowercased()
        return SettingsLayout.searchIndex.filter { entry in
            guard buildModel.schema.vars[entry.item.name] != nil else { return false }
            if entry.item.label.lowercased().contains(needle) { return true }
            if entry.item.name.lowercased().contains(needle) { return true }
            let hint = buildModel.schema.vars[entry.item.name]?.hint ?? ""
            return hint.lowercased().contains(needle)
        }
    }

    var body: some View {
        let found = matches
        if found.isEmpty {
            ContentUnavailableView.search(text: query)
        } else {
            Form {
                let grouped = Dictionary(grouping: found, by: { $0.category })
                ForEach(grouped.keys.sorted(), id: \.self) { title in
                    Section(title) {
                        ForEach(grouped[title] ?? [], id: \.item.id) { entry in
                            ConfigItemRow(item: entry.item)
                        }
                    }
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Search")
        }
    }
}

// MARK: - General

private struct GeneralPane: View {
    @EnvironmentObject var buildModel: BuildModel
    @AppStorage(PrefKeys.xplanePath) private var xplanePath: String = ""
    @AppStorage(AppearanceSetting.prefKey) private var appearanceRaw: String = AppearanceSetting.system.rawValue
    @StateObject private var showingXPlanePicker = ViewState(false)
    @StateObject private var showingDataPicker = ViewState(false)
    @StateObject private var showingEnginePicker = ViewState(false)

    private var xplaneValid: Bool {
        !xplanePath.isEmpty
            && Installation.looksLikeXPlaneRoot(URL(fileURLWithPath: xplanePath, isDirectory: true))
    }

    var body: some View {
        Form {
            Section("Application") {
                LabeledContent("X-Plane Folder") {
                    HStack {
                        pathText(xplanePath)
                        Button("Choose…") { showingXPlanePicker.value = true }
                            .fileImporter(isPresented: $showingXPlanePicker.value,
                                          allowedContentTypes: [.folder]) { result in
                                if case .success(let url) = result { xplanePath = url.path }
                            }
                    }
                }
                if !xplanePath.isEmpty {
                    LabeledContent("Status") {
                        Label(xplaneValid ? "Looks like an X-Plane installation" : "Not recognized as X-Plane",
                              systemImage: xplaneValid ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                            .foregroundStyle(xplaneValid ? .green : .orange)
                    }
                }
                LabeledContent("Data Folder") {
                    HStack {
                        pathText(buildModel.dataRootPath)
                        Button("Choose…") { showingDataPicker.value = true }
                            .fileImporter(isPresented: $showingDataPicker.value,
                                          allowedContentTypes: [.folder]) { result in
                                if case .success(let url) = result { buildModel.dataRootPath = url.path }
                            }
                    }
                }
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

            Section {
                LabeledContent("Engine") {
                    HStack {
                        if buildModel.enginePath.isEmpty {
                            Text(buildModel.usingBundledEngine ? "Bundled with the app" : "Bundled engine missing")
                                .foregroundStyle(buildModel.usingBundledEngine
                                                 ? AnyShapeStyle(.primary) : AnyShapeStyle(.orange))
                        } else {
                            pathText(buildModel.enginePath)
                        }
                        Button("Choose Custom…") { showingEnginePicker.value = true }
                            .fileImporter(isPresented: $showingEnginePicker.value,
                                          allowedContentTypes: [.folder]) { result in
                                if case .success(let url) = result { buildModel.enginePath = url.path }
                            }
                        if !buildModel.enginePath.isEmpty {
                            Button("Use Bundled") { buildModel.enginePath = "" }
                        }
                    }
                }
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
                if let engine = buildModel.engine {
                    LabeledContent("Runtime") {
                        if engine.isFrozen {
                            Label("Self-contained — no Python setup needed",
                                  systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        } else {
                            runtimeStatus(engine: engine)
                        }
                    }
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
            } header: {
                Text("Ortho4XP")
            } footer: {
                Text("XPTerrainBuilder ships with its own copy of the Ortho4XP engine and uses it by default. Point it at a checkout of the engine instead to run a custom version.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Engine Defaults") {
                ForEach(SettingsLayout.engineGeneral) { item in
                    ConfigItemRow(item: item)
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("General")
    }

    private func pathText(_ path: String) -> some View {
        Text(path.isEmpty ? "Not set" : path)
            .lineLimit(1)
            .truncationMode(.middle)
            .foregroundStyle(path.isEmpty ? .secondary : .primary)
            .help(path)
    }

    @ViewBuilder
    private func runtimeStatus(engine: OrthoEngine) -> some View {
        HStack {
            if let missing = buildModel.missingPackages {
                if missing.isEmpty {
                    Label(engine.hasVenv ? "Engine venv — ready" : "System python3 — ready",
                          systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Label("Missing python packages: \(missing.joined(separator: ", "))",
                          systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                }
            } else {
                Text("Checking…").foregroundStyle(.secondary)
            }
            Button("Setup…") { runInstallScript(engine: engine) }
                .help("Opens Terminal running install_mac.sh — installs Homebrew packages and the engine's python environment.")
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

// MARK: - Engine categories

private struct CategoryPane: View {
    @EnvironmentObject var buildModel: BuildModel
    let category: SettingCategory

    var body: some View {
        let _ = buildModel.tileConfigGeneration
        let known = category.items.filter { buildModel.schema.vars[$0.name] != nil }
        let overriddenNames = buildModel.selected.isEmpty ? [] : buildModel.overriddenNames()
        let overridden = known.filter { $0.scope == .tile && overriddenNames.contains($0.name) }
        Form {
            // The selection's customizations for this category, pinned on
            // top with one-click revert (Qt's "This tile" section).
            if !overridden.isEmpty {
                Section("Selected Overrides") {
                    ForEach(overridden) { item in
                        ConfigItemRow(item: item, showsRevert: true)
                    }
                    Button("Reset All to Global") {
                        buildModel.revertTileOverrides(for: overridden.map(\.name))
                    }
                }
            }
            Section(category.title) {
                ForEach(known.filter { !$0.advanced }) { item in
                    ConfigItemRow(item: item)
                }
            }
            let advanced = known.filter { $0.advanced }
            if !advanced.isEmpty {
                Section("Advanced") {
                    ForEach(advanced) { item in
                        ConfigItemRow(item: item)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle(category.title)
    }
}

// MARK: - Rows

/// One schema-driven settings row: allowed-values list → picker, bool →
/// toggle, everything else → a commit-on-return text field. In override
/// listings (`showsRevert`) a revert button restores the global value.
private struct ConfigItemRow: View {
    @EnvironmentObject var buildModel: BuildModel
    let item: SettingItem
    var showsRevert = false

    private var variable: OrthoConfigSchema.Variable? { buildModel.schema.vars[item.name] }

    var body: some View {
        if let variable {
            // Reading tileConfigGeneration subscribes the row to override
            // rewrites without polling files outside selection changes.
            let _ = buildModel.tileConfigGeneration
            HStack(spacing: 8) {
                control(variable)
                if showsRevert {
                    Button {
                        buildModel.revertTileOverrides(for: item.name)
                    } label: {
                        Image(systemName: "arrow.uturn.backward.circle")
                    }
                    .buttonStyle(.borderless)
                    .help("Revert to the global value")
                }
            }
            .help(variable.hint.isEmpty ? item.name : variable.hint)
        }
    }

    private var current: O4Value? { buildModel.effectiveValue(for: item) }

    /// Settings that are filesystem paths get a Choose… button (Qt parity:
    /// its browse buttons). custom_dem picks a FILE; the rest are folders.
    private static let folderSettings: Set<String> = [
        "custom_scenery_dir", "custom_overlay_src",
        "custom_overlay_src_alternate", "cifp_data_path",
    ]
    private static let fileSettings: Set<String> = ["custom_dem"]

    @ViewBuilder
    private func control(_ variable: OrthoConfigSchema.Variable) -> some View {
        if item.name == "base_elevation_source" {
            // Options are files (Providers/Elevation/*.elv), not registry
            // values — enumerate them into a picker.
            Picker(item.label, selection: Binding(
                get: { current?.cfgLiteral ?? "auto" },
                set: { buildModel.setValue(for: item, to: .string($0)) }
            )) {
                ForEach(buildModel.elevationSourceOptions, id: \.self) { option in
                    Text(option == "auto" ? "Auto — best available source" : option)
                        .tag(option)
                }
            }
        } else if Self.folderSettings.contains(item.name)
                    || Self.fileSettings.contains(item.name) {
            PathSettingRow(
                label: item.label,
                current: current?.cfgLiteral ?? "",
                picksDirectories: Self.folderSettings.contains(item.name),
                // custom_dem supports multiple rasters, ";"-separated —
                // picking appends, matching the Qt UI's DEM browser.
                appendsWithSemicolon: item.name == "custom_dem",
                commit: { path in buildModel.setValue(for: item, to: .string(path)) })
        } else if let values = variable.values, !values.isEmpty {
            Picker(item.label, selection: Binding(
                get: { current?.cfgLiteral ?? variable.default.cfgLiteral },
                set: { raw in
                    if let value = O4Value.parse(raw, typeName: variable.type) {
                        buildModel.setValue(for: item, to: value)
                    }
                }
            )) {
                ForEach(values, id: \.self) { value in
                    Text(variable.label(forValue: value)).tag(value)
                }
            }
        } else if variable.type == "bool" {
            Toggle(item.label, isOn: Binding(
                get: { current?.boolValue ?? false },
                set: { buildModel.setValue(for: item, to: .bool($0)) }
            ))
        } else {
            ConfigTextRow(
                label: item.label,
                typeName: variable.type,
                current: current?.cfgLiteral ?? "",
                commit: { raw in
                    guard let value = O4Value.parse(raw, typeName: variable.type) else { return false }
                    buildModel.setValue(for: item, to: value)
                    return true
                })
        }
    }
}

/// Path setting: editable text plus a Choose… button opening the standard
/// file/folder picker (matching the Qt UI's browse buttons).
private struct PathSettingRow: View {
    let label: String
    let current: String
    let picksDirectories: Bool
    var appendsWithSemicolon = false
    let commit: (String) -> Void

    @StateObject private var showingPicker = ViewState(false)
    @StateObject private var text = ViewState<String?>(nil)

    var body: some View {
        HStack {
            TextField(label, text: Binding(
                get: { text.value ?? current },
                set: { text.value = $0 }
            ))
            .onSubmit {
                if let edited = text.value, edited != current { commit(edited) }
                text.value = nil
            }
            Button("Choose…") { showingPicker.value = true }
                .fileImporter(
                    isPresented: $showingPicker.value,
                    allowedContentTypes: picksDirectories ? [.folder] : [.item]
                ) { result in
                    if case .success(let url) = result {
                        if appendsWithSemicolon, !current.isEmpty {
                            commit(current + ";" + url.path)
                        } else {
                            commit(url.path)
                        }
                    }
                }
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
