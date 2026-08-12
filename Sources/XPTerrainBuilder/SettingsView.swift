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
    @StateObject private var signInTarget = ViewState<O4ProviderAccount?>(nil)

    private var xplaneValid: Bool {
        !xplanePath.isEmpty
            && Installation.looksLikeXPlaneRoot(URL(fileURLWithPath: xplanePath, isDirectory: true))
    }

    var body: some View {
        Form {
            Section("Application") {
                LabeledContent("Version") {
                    Text("XPTerrainBuilder \(AppVersion.current)")
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                        .help("Include this when reporting a problem.")
                }
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

            if !buildModel.providerAccounts.isEmpty {
                Section {
                    ForEach(buildModel.providerAccounts) { account in
                        ProviderAccountRow(account: account) {
                            signInTarget.value = account
                        }
                    }
                } header: {
                    Text("Provider Accounts")
                } footer: {
                    Text("These data sources need a signed-in account.  Sessions are kept alive automatically once you sign in.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Engine Defaults") {
                ForEach(SettingsLayout.engineGeneral) { item in
                    ConfigItemRow(item: item)
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("General")
        .task { await buildModel.refreshProviderAccounts() }
        .sheet(item: $signInTarget.value) { account in
            ProviderSignInSheet(account: account)
                .environmentObject(buildModel)
        }
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

// MARK: - Provider accounts

/// One provider account row: who the service is, the codes that share the
/// account, its status, and ONE context-aware control. Status comes from the
/// engine (`auth_providers`) — building this pane never touches the network,
/// and the sign-in itself runs engine-side.
///
/// The row shows the action that applies to the state it is in, never both:
/// a session provider offers "Sign in…" (sheet) or "Sign out" (direct); an
/// api_key provider offers "Add API Key…" or "Edit…", both the same sheet.
/// Ellipsis follows the macOS convention — it marks the actions that open
/// the sheet, and only those.
private struct ProviderAccountRow: View {
    @EnvironmentObject var buildModel: BuildModel
    let account: O4ProviderAccount
    let signIn: () -> Void

    /// A sign-out command is in flight. The outcome lands as a
    /// `SignInResult`, which refreshes the rows — this only holds the
    /// control disabled for the command's own round trip, so a refused
    /// command (no event follows) can never leave the row stuck.
    @StateObject private var signingOut = ViewState(false)

    /// The store-derived status has not landed yet (an api_key row is read
    /// on an engine worker thread): show the not-signed-in wording rather
    /// than guess, and let the disabled state say "ask again shortly".
    private var pending: Bool { account.statusPending }

    /// Signed-in wording is only earned once the status is real.
    private var established: Bool { account.signedIn && !pending }

    private var buttonTitle: String {
        if account.isAPIKey { return established ? "Edit…" : "Add API Key…" }
        return established ? "Sign out" : "Sign in…"
    }

    /// Sign-out is the one action that acts directly; everything else opens
    /// the existing sheet (which forces Remember on for an api_key).
    private func act() {
        guard established, !account.isAPIKey else { return signIn() }
        signingOut.value = true
        Task {
            await buildModel.providerSignOut(sessionName: account.sessionName)
            signingOut.value = false
        }
    }

    var body: some View {
        LabeledContent {
            // The status text is the only elastic part of the row: it takes
            // the slack (right-aligned against the control) and truncates
            // when a long "Signed in as …" would otherwise widen the row.
            // The button is fixed-size and outranks it, so every row's
            // control shares one trailing edge in every state — a signed-in
            // row used to push its buttons left. Same idiom as
            // `PathSettingRow`, with the full string in the tooltip.
            HStack(spacing: 10) {
                Text(account.statusText)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .foregroundStyle(account.signedIn ? AnyShapeStyle(.green)
                                     : AnyShapeStyle(.secondary))
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .help(account.statusText)
                Button(buttonTitle, action: act)
                    .disabled(pending || signingOut.value)
                    .fixedSize()
                    .layoutPriority(1)
            }
        } label: {
            VStack(alignment: .leading, spacing: 1) {
                Text(account.title)
                if !account.codes.isEmpty {
                    Text(account.codes.joined(separator: ", "))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .help(account.registrationURL.isEmpty ? ""
                  : "Create an account: \(account.registrationURL)")
        }
    }
}

/// The credentials prompt, ported from the Qt settings window's
/// `_SignInDialog` (copy and behaviour are its authority). The password or
/// key lives only here and in the one command send: the engine performs the
/// login and, with Remember, stores the secret in THIS app's Keychain
/// through the brokered secret protocol.
private struct ProviderSignInSheet: View {
    @EnvironmentObject var buildModel: BuildModel
    let account: O4ProviderAccount
    @Environment(\.dismiss) private var dismiss

    @StateObject private var username = ViewState("")
    @StateObject private var secret = ViewState("")
    @StateObject private var remember = ViewState(true)
    @StateObject private var errorText = ViewState("")
    @StateObject private var busy = ViewState(false)
    @FocusState private var secretFocused: Bool

    private var introduction: String {
        account.isAPIKey
            ? "This provider requires a (free) account at \(account.serviceHost) and an API key generated there.  Paste the key below; it is stored in the system keychain."
            : "This provider requires a (free) account at \(account.serviceHost).  Your password is sent only to that service."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Sign in — \(account.sheetTitle)")
                .font(.headline)
            Text(introduction)
                .fixedSize(horizontal: false, vertical: true)

            if let registration = URL(string: account.registrationURL),
               !account.registrationURL.isEmpty {
                Link("No account yet?  Create one here.", destination: registration)
            }

            if !account.setupSteps.isEmpty {
                // Some accounts need work before credentials will work at
                // all (Sweden: order the free product; Denmark: copy a
                // token) — the checklist belongs right here.
                Text("Setup").bold()
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(account.setupSteps.enumerated()), id: \.offset) { step in
                        HStack(alignment: .top, spacing: 6) {
                            Text("\(step.offset + 1).")
                                .foregroundStyle(.secondary)
                            Text(linkified(step.element))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(.leading, 4)
            }

            if !account.isAPIKey {
                TextField("Username or email address", text: $username.value)
                    .disabled(busy.value)
            }
            SecureField(account.isAPIKey ? "API key" : "Password", text: $secret.value)
                .focused($secretFocused)
                .disabled(busy.value)

            if !account.isAPIKey {
                // An API key only works stored: it is read back at build
                // time, unlike a session which persists as cookies — so
                // that kind forces Remember on and hides the control.
                Toggle("Remember on this device (stored in the system keychain)",
                       isOn: $remember.value)
                    .disabled(busy.value || !account.credentialStoreAvailable)
                    .help(account.credentialStoreAvailable ? ""
                          : "No system keychain is available on this machine; the session lasts until it expires, then sign in again.")
            }

            if !errorText.value.isEmpty {
                Text(errorText.value)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(busy.value ? "Signing in…" : "Sign in") { startSignIn() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(busy.value)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onAppear {
            remember.value = account.isAPIKey || account.credentialStoreAvailable
        }
        .onChange(of: buildModel.lastSignInResult?.id) {
            guard let result = buildModel.lastSignInResult,
                  result.sessionName == account.sessionName, busy.value
            else { return }
            if result.ok {
                dismiss()
                return
            }
            errorText.value = result.errorText
            busy.value = false
            secretFocused = true
        }
    }

    private func startSignIn() {
        let key = secret.value
        if account.isAPIKey {
            guard !key.trimmingCharacters(in: .whitespaces).isEmpty else {
                errorText.value = "Paste an API key."
                return
            }
        } else if username.value.trimmingCharacters(in: .whitespaces).isEmpty
                    || key.isEmpty {
            errorText.value = "Enter both a username and a password."
            return
        }
        errorText.value = ""
        busy.value = true
        let name = account.sessionName
        let user = account.isAPIKey ? ""
            : username.value.trimmingCharacters(in: .whitespaces)
        let wantsRemember = account.isAPIKey || remember.value
        Task {
            if let failure = await buildModel.providerSignIn(
                sessionName: name, username: user, secret: key,
                remember: wantsRemember) {
                errorText.value = failure
                busy.value = false
                secretFocused = true
            }
        }
    }

    /// Any http(s) URL inside a setup step becomes a link (the Qt dialog's
    /// `_linkify_urls` behaviour).
    private func linkified(_ text: String) -> AttributedString {
        var attributed = AttributedString(text)
        guard let detector = try? NSDataDetector(
            types: NSTextCheckingResult.CheckingType.link.rawValue) else {
            return attributed
        }
        let whole = NSRange(text.startIndex..<text.endIndex, in: text)
        detector.enumerateMatches(in: text, range: whole) { match, _, _ in
            guard let match, let url = match.url,
                  url.scheme == "http" || url.scheme == "https",
                  let stringRange = Range(match.range, in: text),
                  let range = Range(stringRange, in: attributed) else { return }
            attributed[range].link = url
        }
        return attributed
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

/// Path setting: shows the chosen path (middle-truncated) once set, with a
/// compact folder button to pick a new one and an ✕ to clear; an unset row
/// shows a "Choose…" button.
private struct PathSettingRow: View {
    let label: String
    let current: String
    let picksDirectories: Bool
    var appendsWithSemicolon = false
    let commit: (String) -> Void

    @StateObject private var showingPicker = ViewState(false)

    var body: some View {
        LabeledContent(label) {
            HStack(spacing: 6) {
                if current.isEmpty {
                    Text("Not set")
                        .foregroundStyle(.secondary)
                    Button("Choose…") { showingPicker.value = true }
                } else {
                    Text(current)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .frame(maxWidth: 320, alignment: .trailing)
                        .help(current)
                    Button {
                        showingPicker.value = true
                    } label: {
                        Image(systemName: picksDirectories ? "folder" : "doc.badge.plus")
                    }
                    .help(appendsWithSemicolon
                          ? "Add another file (\";\"-separated)" : "Choose a different one")
                    Button {
                        commit("")
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Clear")
                }
            }
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
