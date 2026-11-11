import AppKit
import SwiftUI
import SceneryKit
import UniformTypeIdentifiers

/// `.xptb` packages in the app (#2014; Qt: `O4_Qt_Tile_Package.py`).
///
/// * File ▸ Export Package… (and the map's tile menu) saves the selected
///   tiles' package — whole tiles, or the airports picked in the sheet —
///   with its maker's optional title, name, notes and link.
/// * A package opened on the app icon (double-click in Finder: the app
///   declares the `xptb` type, `make_app.sh`) or dropped on the map is
///   planned by the engine (`package_plan`) and shown in a sheet: its
///   tiles and airports, the packs they match, its sources and terms,
///   and, per airport that already has a patch, "Keep my patch" or "Back
///   up mine and use the package's". Install runs `package_install`.
/// * File ▸ Combine Packages… merges several packages into one.
@MainActor
final class TilePackageModel: ObservableObject {
    static let shared = TilePackageModel()

    struct Install: Identifiable {
        let id = UUID()
        let path: String
        let plan: O4PackagePlan
        var choices: [String: String]
    }

    struct Export: Identifiable {
        let id = UUID()
        let tiles: [BuildModel.TileCoord]
        let airports: [String: [String]]
        var picked: Set<String> = []
        var title = ""
        var creator = ""
        var notes = ""
        var url = ""
    }

    @Published var install: Install?
    @Published var export: Export?
    @Published var message: String?

    static var packageType: UTType {
        UTType(O4TilePackage.typeIdentifier)
            ?? UTType(filenameExtension: O4TilePackage.fileExtension) ?? .data
    }

    private func client(_ build: BuildModel) -> (OrthoEngineClient, String)? {
        guard let context = build.libraryContext() else { return nil }
        let caps = build.engineCapabilities
        if !caps.protocolVersion.isEmpty && !caps.supports(O4EngineCapabilities.tilePackage) {
            message = "This build engine cannot read packages."
            return nil
        }
        return (context.client, context.workingDir)
    }

    // MARK: Install

    func offer(_ urls: [URL], build: BuildModel) {
        guard let path = urls.first?.path, let (client, dir) = client(build) else { return }
        Task {
            do {
                let plan = try await client.packagePlan(path: path, workingDir: dir)
                let choices = Dictionary(plan.conflicts.map { ($0.icao, $0.choice) },
                                         uniquingKeysWith: { a, _ in a })
                install = Install(path: path, plan: plan, choices: choices)
            } catch {
                message = "\(error)"
            }
        }
    }

    func confirm(_ request: Install, build: BuildModel) {
        guard let (client, dir) = client(build) else { return }
        install = nil
        Task {
            do {
                let done = try await client.packageInstall(path: request.path, workingDir: dir,
                                                           choices: request.choices)
                for tile in done.tiles {
                    build.console.append(O4TilePackageCopy.installed(done), tile: tile.tile)
                }
            } catch {
                message = "\(error)"
            }
            build.rescan()
            build.refreshCustomPatchTiles()
        }
    }

    func chooseAndInstall(build: BuildModel) {
        let panel = NSOpenPanel()
        panel.title = "Install Package"
        panel.allowedContentTypes = [Self.packageType,
                                     UTType(filenameExtension: O4TilePackage.legacyExtension) ?? .data]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        offer([url], build: build)
    }

    // MARK: Export

    func startExport(_ tiles: [BuildModel.TileCoord], build: BuildModel) {
        guard !tiles.isEmpty, let (client, dir) = client(build) else { return }
        let sorted = tiles.sorted()
        Task {
            do {
                let found = try await client.packageAirports(
                    tiles: sorted.map { ($0.lat, $0.lon) }, workingDir: dir)
                export = Export(tiles: sorted, airports: found.tiles)
            } catch {
                message = "\(error)"
            }
        }
    }

    func save(_ request: Export, build: BuildModel) {
        guard let (client, dir) = client(build) else { return }
        let panel = NSSavePanel()
        panel.title = "Export Package"
        panel.allowedContentTypes = [Self.packageType]
        panel.nameFieldStringValue = Self.defaultName(request)
        guard panel.runModal() == .OK, let url = panel.url else { return }
        export = nil
        Task {
            do {
                let done = try await client.packageSave(
                    tiles: request.tiles.map { ($0.lat, $0.lon) }, workingDir: dir, out: url.path,
                    airports: request.picked.sorted(), title: request.title,
                    creator: request.creator, notes: request.notes, url: request.url)
                build.console.append("Saved package \(url.lastPathComponent) "
                    + "(\(ByteCountFormatter.string(fromByteCount: done.bytes, countStyle: .file)))"
                    + (done.noncommercial ? ", non-commercial." : "."))
            } catch {
                message = "\(error)"
            }
        }
    }

    static func defaultName(_ request: Export) -> String {
        let first = request.tiles.first?.key ?? "tiles"
        let tail = request.picked.isEmpty
            ? (request.tiles.count == 1 ? first : "\(first)_\(request.tiles.count)tiles")
            : request.picked.sorted().joined(separator: "_")
        return "XPTerrainBuilder_\(tail).\(O4TilePackage.fileExtension)"
    }

    // MARK: Combine

    func combine(build: BuildModel) {
        guard let (client, _) = client(build) else { return }
        let open = NSOpenPanel()
        open.title = "Combine Packages"
        open.allowsMultipleSelection = true
        open.allowedContentTypes = [Self.packageType]
        guard open.runModal() == .OK, open.urls.count > 1 else { return }
        let save = NSSavePanel()
        save.allowedContentTypes = [Self.packageType]
        save.nameFieldStringValue = "XPTerrainBuilder_combined.\(O4TilePackage.fileExtension)"
        guard save.runModal() == .OK, let out = save.url else { return }
        Task {
            do {
                let done = try await client.packageMerge(paths: open.urls.map(\.path), out: out.path)
                build.console.append("Combined \(open.urls.count) packages into "
                    + "\(out.lastPathComponent) (\(done.tiles.joined(separator: ", "))).")
            } catch {
                message = "\(error)"
            }
        }
    }
}

/// The install and export sheets, and the refusal alert, on the map.
struct TilePackageSheets: ViewModifier {
    @ObservedObject var buildModel: BuildModel
    @ObservedObject private var model = TilePackageModel.shared

    func body(content: Content) -> some View {
        content
            .sheet(item: $model.install) { request in
                TilePackageInstallSheet(request: request) { model.confirm($0, build: buildModel) }
            }
            .sheet(item: $model.export) { request in
                TilePackageExportSheet(request: request) { model.save($0, build: buildModel) }
            }
            .alert("Package", isPresented: Binding(
                get: { model.message != nil },
                set: { if !$0 { model.message = nil } }
            )) {
                Button("OK") { model.message = nil }
            } message: {
                Text(model.message ?? "")
            }
    }
}

struct TilePackageInstallSheet: View {
    @State var request: TilePackageModel.Install
    let onInstall: (TilePackageModel.Install) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(O4TilePackageCopy.installTitle).font(.headline)
            if !request.plan.notes.isEmpty { Text(request.plan.notes).foregroundStyle(.secondary) }
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(request.plan.summary.enumerated()), id: \.offset) { _, line in
                        Text(line).textSelection(.enabled)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(minHeight: 120, maxHeight: 260)
            ForEach(request.plan.conflicts) { conflict in
                Picker("\(conflict.icao) (tile \(conflict.tile))", selection: Binding(
                    get: { request.choices[conflict.icao] ?? "keep" },
                    set: { request.choices[conflict.icao] = $0 }
                )) {
                    Text(O4TilePackageCopy.keepMine).tag("keep")
                    Text(O4TilePackageCopy.useTheirs).tag("replace")
                }
                .help("Backed up as \((conflict.backup as NSString).lastPathComponent) in the tile's patch folder")
            }
            if !request.plan.url.isEmpty, let link = URL(string: request.plan.url) {
                Link(request.plan.url, destination: link)
            }
            HStack {
                Spacer()
                Button("Cancel", role: .cancel) { dismiss() }
                Button(O4TilePackageCopy.install) { onInstall(request) }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 520)
    }
}

struct TilePackageExportSheet: View {
    @State var request: TilePackageModel.Export
    let onSave: (TilePackageModel.Export) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Export Package").font(.headline)
            Text("Tiles \(request.tiles.map(\.key).joined(separator: ", ")). Imagery is never "
                 + "included. Pick airports to export only them; none picked exports the "
                 + "whole tiles.")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            ScrollView {
                VStack(alignment: .leading) {
                    ForEach(request.airports.keys.sorted(), id: \.self) { tile in
                        ForEach(request.airports[tile] ?? [], id: \.self) { icao in
                            Toggle("\(icao) (tile \(tile))", isOn: Binding(
                                get: { request.picked.contains(icao) },
                                set: { on in
                                    if on { request.picked.insert(icao) } else { request.picked.remove(icao) }
                                }
                            ))
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 160)
            Form {
                TextField("Title", text: $request.title)
                TextField("Made by", text: $request.creator)
                TextField("Notes", text: $request.notes, axis: .vertical)
                TextField("Link", text: $request.url)
            }
            HStack {
                Spacer()
                Button("Cancel", role: .cancel) { dismiss() }
                Button("Save…") { onSave(request) }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 480)
    }
}

/// File ▸ Export Package… / Install Package… / Combine Packages…
struct TilePackageCommands: View {
    @ObservedObject var buildModel: BuildModel

    var body: some View {
        Button(O4TilePackageCopy.exportTitle) {
            TilePackageModel.shared.startExport(Array(buildModel.selected), build: buildModel)
        }
        .disabled(buildModel.selected.isEmpty)
        Button("Install Package…") { TilePackageModel.shared.chooseAndInstall(build: buildModel) }
        Button(O4TilePackageCopy.combineTitle) { TilePackageModel.shared.combine(build: buildModel) }
    }
}
