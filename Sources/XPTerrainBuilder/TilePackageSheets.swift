import AppKit
import SwiftUI
import SceneryKit
import UniformTypeIdentifiers

/// `.xptb` packages in the app (#2014; Qt: `O4_Qt_Tile_Package.py`).
///
/// * File ▸ Export Package… (and the map's tile menu) is AIRPORT-FIRST
///   (owner 2026-11-11T16:10Z): pick one airport (it opens on the one with
///   a custom patch), then a kind — Exact match, Airport patch only, or
///   Whole tile (last) — each with its explanation, estimated size, and
///   the recipient's downloads and build time (`package_estimate`), and
///   the maker's optional title, name, notes and link.
/// * A package opened on the app icon (double-click in Finder: the app
///   declares the `xptb` type, `make_app.sh`) or dropped on the map is
///   planned by the engine (`package_plan`) and shown in a sheet: its
///   tiles and airports, the packs they match, its sources and terms,
///   and, per airport that already has a patch, "Keep my patch" or "Back
///   up mine and use the package's". Install runs `package_install`.
/// * File ▸ Combine Packages… merges several packages into one.
/// * For an airport served by the user's own Custom Scenery pack, the
///   export window also says what the pack's author wants for its
///   objects — "Objects are final" or "Apply XPTerrainBuilder's object
///   fixes into my pack…" (`package_developer`, RULINGS 2026-11-11m (3))
///   — and can save the package into the pack's own folder, where every
///   installation applies it as the airport's tiles build.
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
        let airports: [String]
        let custom: Set<String>
        /// The airport exported; "" exports the whole tiles.
        var airport: String
        /// "exact", "patch" or "tile" (`tile_bundle.kinds`).
        var kind: String
        var estimate: O4PackageEstimate?
        var title = ""
        var creator = ""
        var notes = ""
        var url = ""
        /// The airport's own pack (nil: Global Airports, or not read yet).
        var developer: O4PackageDeveloper?
        /// Save into `<pack>/XPTerrainBuilder/<ICAO>.xptb`.
        var intoPack = false

        /// The chosen kind's estimate row, when estimated.
        var chosen: O4PackageKindEstimate? { estimate?.kinds.first { $0.kind == kind } }
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

    func startExport(_ tiles: [BuildModel.TileCoord], build: BuildModel, airport: String? = nil) {
        guard !tiles.isEmpty, let (client, dir) = client(build) else { return }
        let sorted = tiles.sorted()
        Task {
            do {
                let found = try await client.packageAirports(
                    tiles: sorted.map { ($0.lat, $0.lon) }, workingDir: dir)
                let all = found.all
                let start = airport.flatMap { all.contains($0) ? $0 : nil } ?? found.default ?? ""
                export = Export(tiles: sorted, airports: all,
                                custom: Set((found.custom ?? [:]).values.joined()),
                                airport: start, kind: start.isEmpty ? "tile" : "exact")
                estimate(build: build)
                developer(build: build)
            } catch {
                message = "\(error)"
            }
        }
    }

    /// The export window's airport changed: every kind is estimated again.
    func choose(airport: String, build: BuildModel) {
        guard var request = export, request.airport != airport else { return }
        request.airport = airport
        request.kind = airport.isEmpty ? "tile" : "exact"
        request.estimate = nil
        request.developer = nil
        request.intoPack = false
        export = request
        estimate(build: build)
        developer(build: build)
    }

    /// The chosen airport's pack and its author's objects choice; `action`
    /// "final", "default" or "apply" changes it (RULINGS 2026-11-11m (3)).
    func developer(build: BuildModel, action: String = "read") {
        guard let request = export, !request.airport.isEmpty,
              build.engineCapabilities.supports(O4EngineCapabilities.packPackages),
              let (client, dir) = client(build) else { return }
        if action == "apply" {
            let alert = NSAlert()
            alert.messageText = O4TilePackageCopy.applyFixes
            alert.informativeText = O4TilePackageCopy.applyConfirm
            alert.addButton(withTitle: "Apply")
            alert.addButton(withTitle: "Cancel")
            guard alert.runModal() == .alertFirstButtonReturn else { return }
        }
        Task {
            do {
                let found = try await client.packageDeveloper(
                    icao: request.airport, tiles: request.tiles.map { ($0.lat, $0.lon) },
                    workingDir: dir, action: action)
                if export?.id == request.id, export?.airport == request.airport {
                    export?.developer = found
                }
                if action != "read" {
                    build.console.append("\(found.pack): objects "
                        + (found.objects.isEmpty ? "fitted by XPTerrainBuilder" : found.objects)
                        + (found.moved > 0 ? " (\(found.moved) originals moved to its backup folder)" : "")
                        + (found.restored > 0 ? " (\(found.restored) originals put back)" : "") + ".")
                }
            } catch {
                if action != "read" { message = "\(error)" }   // no pack of yours: no row
            }
        }
    }

    private func estimate(build: BuildModel) {
        guard let request = export, let (client, dir) = client(build) else { return }
        Task {
            do {
                let found = try await client.packageEstimate(
                    tiles: request.tiles.map { ($0.lat, $0.lon) }, workingDir: dir,
                    airport: request.airport)
                if export?.id == request.id, export?.airport == request.airport {
                    export?.estimate = found
                }
            } catch {
                message = "\(error)"
            }
        }
    }

    func save(_ request: Export, build: BuildModel) {
        guard let (client, dir) = client(build) else { return }
        var url = URL(fileURLWithPath: request.developer.map {
            "\($0.packRoot)/XPTerrainBuilder/\(request.airport).\(O4TilePackage.fileExtension)"
        } ?? "")
        if !request.intoPack {
            let panel = NSSavePanel()
            panel.title = "Export Package"
            panel.allowedContentTypes = [Self.packageType]
            panel.nameFieldStringValue = Self.defaultName(request)
            guard panel.runModal() == .OK, let chosen = panel.url else { return }
            url = chosen
        }
        export = nil
        Task {
            do {
                let done = try await client.packageSave(
                    tiles: request.tiles.map { ($0.lat, $0.lon) }, workingDir: dir, out: url.path,
                    airports: request.kind == "tile" ? [] : [request.airport],
                    kind: request.kind, title: request.title,
                    creator: request.creator, notes: request.notes, url: request.url,
                    intoPack: request.intoPack)
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
        let tail = request.kind == "tile" || request.airport.isEmpty
            ? (request.tiles.count == 1 ? first : "\(first)_\(request.tiles.count)tiles")
            : "\(request.airport)_\(request.kind)"
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
            .sheet(item: $model.export) { _ in
                TilePackageExportSheet(model: model, buildModel: buildModel)
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
    @ObservedObject var model: TilePackageModel
    @ObservedObject var buildModel: BuildModel
    @Environment(\.dismiss) private var dismiss

    private func field(_ path: WritableKeyPath<TilePackageModel.Export, String>) -> Binding<String> {
        Binding(get: { model.export?[keyPath: path] ?? "" },
                set: { model.export?[keyPath: path] = $0 })
    }

    var body: some View {
        if let request = model.export {
            VStack(alignment: .leading, spacing: 10) {
                Text("Export Package").font(.headline)
                Picker(O4TilePackageCopy.airportLabel, selection: Binding(
                    get: { request.airport },
                    set: { model.choose(airport: $0, build: buildModel) }
                )) {
                    ForEach(request.airports, id: \.self) { icao in
                        Text(request.custom.contains(icao) ? "\(icao) (custom patch)" : icao).tag(icao)
                    }
                    Text(O4TilePackageCopy.wholeTileOnly).tag("")
                }
                if let estimate = request.estimate {
                    ForEach(estimate.kinds) { row in
                        kindRow(row, chosen: row.kind == request.kind)
                    }
                } else {
                    ProgressView("Estimating sizes…").controlSize(.small)
                }
                Text(O4TilePackageCopy.estimateNote).font(.caption).foregroundStyle(.secondary)
                if let pack = request.developer {
                    developerRows(pack, request: request)
                }
                Form {
                    TextField("Title", text: field(\.title))
                    TextField("Made by", text: field(\.creator))
                    TextField("Notes", text: field(\.notes), axis: .vertical)
                    TextField("Link", text: field(\.url))
                }
                HStack {
                    Spacer()
                    Button("Cancel", role: .cancel) { dismiss() }
                    Button("Save…") { model.save(request, build: buildModel) }
                        .keyboardShortcut(.defaultAction)
                        .disabled(!(request.chosen?.available ?? false))
                }
            }
            .padding(20)
            .frame(width: 520)
        }
    }

    /// The pack author's rows (RULINGS 2026-11-11m (3); Qt: the same three
    /// controls in `_ExportDialog`).
    @ViewBuilder
    private func developerRows(_ pack: O4PackageDeveloper, request: TilePackageModel.Export) -> some View {
        Divider()
        Text("Your pack: \(pack.pack)").bold()
        Picker(O4TilePackageCopy.objectsLabel, selection: Binding(
            get: { pack.objects },
            set: { model.developer(build: buildModel, action: $0 == "final" ? "final" : "default") }
        )) {
            Text(O4TilePackageCopy.objectsDefault).tag("")
            Text(O4TilePackageCopy.objectsFinal).tag("final")
            if pack.objects == "applied" { Text(O4TilePackageCopy.objectsApplied).tag("applied") }
        }
        Button(O4TilePackageCopy.applyFixes) { model.developer(build: buildModel, action: "apply") }
            .disabled(!pack.modified)
        Toggle(O4TilePackageCopy.intoPack, isOn: Binding(
            get: { request.intoPack },
            set: { model.export?.intoPack = $0 }
        ))
        .disabled(request.kind == "tile")
        Divider()
    }

    private func kindRow(_ row: O4PackageKindEstimate, chosen: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: chosen ? "largecircle.fill.circle" : "circle")
                .foregroundStyle(row.available ? Color.accentColor : Color.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(row.title).bold()
                Text(row.explanation).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(row.available ? row.figures : row.why).font(.caption)
                    .foregroundStyle(row.available ? Color.secondary : Color.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            guard row.available else { return }
            model.export?.kind = row.kind
            if row.kind == "tile" { model.export?.intoPack = false }
        }
        .opacity(row.available ? 1 : 0.6)
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
