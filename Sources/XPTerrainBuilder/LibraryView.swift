import AppKit
import SwiftUI
import SceneryKit
import UniformTypeIdentifiers

/// The Library window (#824): every built tile with its size, zoom level,
/// imagery source, built date, graded airports, modified packs and the
/// "In X-Plane" switch, plus the disk panel (tiles total and each download
/// cache with "Free space…"). The engine's `library_*` commands do the
/// folder walks; the Qt app's `O4_Qt_Library` shows the same columns.
/// A tile built by another tool is read-only: it can be linked into
/// X-Plane or out of it, never rebuilt or deleted. Deleting and freeing
/// space ask first. Export / Import Library Bundle carry a built tile to
/// another installation (#1699 phase 1; the Qt dialog has the same two).
/// The "Patch library" section and "Publish Patch…" are the shared patch
/// library (#1699 phase 2, `PatchLibraryView.swift`).
enum Library {
    static let windowID = "library"
    /// A tile bundle's file extension (`tile_bundle.export.BUNDLE_SUFFIX`).
    static let bundleExtension = "xptbundle"

    static func size(_ bytes: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }

    static func date(_ unix: Double?) -> String {
        guard let unix else { return "—" }
        return Date(timeIntervalSince1970: unix).formatted(date: .numeric, time: .shortened)
    }
}

@MainActor
final class LibraryModel: ObservableObject {
    @Published var tiles: [O4LibraryTile] = []
    @Published var caches: [O4LibraryCache] = []
    @Published var tilesBytes: Int64 = 0
    @Published var isLoading = false
    @Published var status = ""

    func refresh(_ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext() else {
            status = "The engine is not running."
            return
        }
        isLoading = true
        status = "Reading tiles…"
        Task {
            do {
                let scan = try await context.client.libraryScan(
                    workingDir: context.workingDir, sceneryDir: context.sceneryDir)
                tiles = scan.tiles
                caches = scan.caches
                tilesBytes = scan.tilesBytes
                status = ""
            } catch {
                status = "\(error)"
            }
            isLoading = false
        }
    }

    func delete(_ rows: [O4LibraryTile], _ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext(), !rows.isEmpty else { return }
        status = "Deleting…"
        Task {
            do {
                let freed = try await context.client.libraryDelete(
                    tiles: rows.map { (lat: $0.lat, lon: $0.lon) },
                    workingDir: context.workingDir, sceneryDir: context.sceneryDir)
                status = "Deleted \(rows.count) tile(s), freed \(Library.size(freed.freedBytes))."
            } catch {
                status = "\(error)"
            }
            buildModel.rescan()
            refresh(buildModel)
        }
    }

    func freeCache(_ cache: O4LibraryCache, _ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext() else { return }
        status = "Freeing space…"
        Task {
            do {
                let freed = try await context.client.freeCache(kind: cache.kind)
                status = "Freed \(Library.size(freed.freedBytes)) of \(cache.label.lowercased()) cache."
            } catch {
                status = "\(error)"
            }
            refresh(buildModel)
        }
    }

    func exportBundle(_ row: O4LibraryTile, _ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext() else { return }
        let panel = NSOpenPanel()
        panel.title = "Export Library Bundle"
        panel.prompt = "Export Here"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let folder = panel.url else { return }
        status = "Exporting \(row.tile)…"
        Task {
            do {
                let done = try await context.client.libraryExportBundle(
                    lat: row.lat, lon: row.lon, workingDir: context.workingDir, outDir: folder.path)
                status = "Exported \(row.tile) (\(Library.size(done.bytes)))."
            } catch {
                status = "\(error)"
            }
        }
    }

    func importBundle(_ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext() else { return }
        let panel = NSOpenPanel()
        panel.title = "Import Library Bundle"
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [UTType(filenameExtension: Library.bundleExtension) ?? .data]
        guard panel.runModal() == .OK, let file = panel.url else { return }
        status = "Importing \(file.lastPathComponent)…"
        Task {
            do {
                let done = try await context.client.libraryImportBundle(
                    path: file.path, workingDir: context.workingDir)
                status = "Imported \(done.tile). Build it to add your imagery."
            } catch {
                status = "\(error)"
            }
            buildModel.rescan()
            refresh(buildModel)
        }
    }

    func restoreOriginals(_ packs: [O4LibraryPack], _ buildModel: BuildModel) {
        status = "Restoring originals…"
        Task {
            var failures: [String] = []
            for pack in packs {
                let outcome = await buildModel.reanchorRestore(packPath: pack.packPath)
                if let error = outcome.error { failures.append("\(pack.packName): \(error)") }
            }
            status = failures.isEmpty
                ? "Restored \(packs.count) pack(s)."
                : failures.joined(separator: "; ")
            refresh(buildModel)
        }
    }
}

struct LibraryView: View {
    @EnvironmentObject private var buildModel: BuildModel
    @StateObject private var model = LibraryModel()
    @State private var selection = Set<O4LibraryTile.ID>()
    @State private var search = ""
    @State private var sortOrder = [KeyPathComparator(\O4LibraryTile.tile)]
    @State private var confirmDelete = false
    @State private var confirmRestore = false
    @State private var cacheToFree: O4LibraryCache?
    @State private var publishing: O4LibraryTile?

    private var shown: [O4LibraryTile] {
        let query = search.lowercased()
        return model.tiles.filter { $0.matches(query) }.sorted(using: sortOrder)
    }

    private var selectedRows: [O4LibraryTile] {
        model.tiles.filter { selection.contains($0.id) }
    }

    private var selectedPacks: [O4LibraryPack] {
        Array(Set(selectedRows.flatMap(\.packsModified))).sorted { $0.packName < $1.packName }
    }

    private var writable: Bool {
        !selectedRows.isEmpty && !selectedRows.contains(where: \.readOnly)
    }

    var body: some View {
        VStack(spacing: 0) {
            table
            Divider()
            actions.padding(8)
            Divider()
            PatchLibrarySection().padding(8)
            Divider()
            diskPanel.padding(8)
        }
        .frame(minWidth: 820, minHeight: 460)
        .searchable(text: $search, prompt: "Search tiles, airports, imagery")
        .toolbar {
            ToolbarItem {
                Button { model.refresh(buildModel) } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Read the tiles folder and the caches again")
                .disabled(model.isLoading)
            }
        }
        .onAppear { model.refresh(buildModel) }
        .sheet(item: $publishing) { tile in PublishPatchSheet(tile: tile) }
        .onChange(of: buildModel.installed) { _, _ in model.refresh(buildModel) }
        .confirmationDialog("Delete \(selectedRows.count) tile(s)?", isPresented: $confirmDelete) {
            Button("Delete", role: .destructive) { model.delete(selectedRows, buildModel) }
        } message: {
            Text(deleteMessage)
        }
        .confirmationDialog("Restore originals?", isPresented: $confirmRestore) {
            Button("Restore") { model.restoreOriginals(selectedPacks, buildModel) }
        } message: {
            Text("Put back the original object files of \(selectedPacks.map(\.packName).joined(separator: ", ")).")
        }
        .confirmationDialog("Free space?", isPresented: Binding(
            get: { cacheToFree != nil }, set: { if !$0 { cacheToFree = nil } })) {
            Button("Free Space", role: .destructive) {
                if let cache = cacheToFree { model.freeCache(cache, buildModel) }
            }
        } message: {
            if let cache = cacheToFree {
                Text("Free \(Library.size(cache.bytes)) of \(cache.label.lowercased()) cache? \(cache.redownload)")
            }
        }
    }

    private var deleteMessage: String {
        let bytes = selectedRows.reduce(Int64(0)) { $0 + $1.sizeBytes }
        var text = "Their folders (\(Library.size(bytes))) are deleted and they are taken out of "
            + "X-Plane. Your airport patches and the download caches stay."
        let packs = selectedPacks.map(\.packName)
        if !packs.isEmpty {
            text += "\n\nThese custom packs stay modified for the deleted ground: "
                + packs.joined(separator: ", ") + ". Use Restore Originals first to put them back."
        }
        return text
    }

    // MARK: - Table (columns as O4_Qt_Library.COLUMNS)

    private var table: some View {
        Table(shown, selection: $selection, sortOrder: $sortOrder) {
            TableColumn("Tile", value: \.tile) { row in
                Text(row.tile).monospacedDigit()
                    .foregroundStyle(row.readOnly ? .secondary : .primary)
            }
            TableColumn("Size", value: \.sizeBytes) { row in
                Text(Library.size(row.sizeBytes)).monospacedDigit()
            }
            TableColumn("ZL", value: \.zlSortKey) { row in
                Text(row.zl.map(String.init) ?? "")
            }
            .width(min: 30, ideal: 36)
            TableColumn("Imagery", value: \.provider)
            TableColumn("Built", value: \.builtSortKey) { row in
                Text(Library.date(row.built))
            }
            TableColumn("Airports", value: \.airportsText)
            TableColumn("Packs modified", value: \.packsText)
            TableColumn("In X-Plane", value: \.inXPlaneSortKey) { row in
                Toggle("", isOn: Binding(
                    get: { row.inXPlane },
                    set: { buildModel.setInstalled(BuildModel.TileCoord(lat: row.lat, lon: row.lon), $0) }))
                .labelsHidden()
                .toggleStyle(.checkbox)
            }
            .width(min: 60, ideal: 70)
            TableColumn("Built by", value: \.builtByText)
        }
    }

    // MARK: - Actions

    private var actions: some View {
        HStack {
            Button("Install") { setInstalled(true) }
                .disabled(selectedRows.isEmpty)
            Button("Uninstall") { setInstalled(false) }
                .disabled(selectedRows.isEmpty)
            Button("Rebuild") {
                buildModel.rebuild(selectedRows.map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) })
            }
            .disabled(!writable)
            Button("Delete…") { confirmDelete = true }
                .disabled(!writable || buildModel.isBuilding)
            Button("Restore Originals…") { confirmRestore = true }
                .help("Put back the original object files of the custom packs these tiles' builds modified")
                .disabled(selectedPacks.isEmpty || buildModel.isBuilding)
            Button("Export Library Bundle…") {
                if let row = selectedRows.first { model.exportBundle(row, buildModel) }
            }
            .help("Write this tile's mesh, masks and solved airports to a bundle another installation can import")
            .disabled(selectedRows.count != 1 || !writable || buildModel.isBuilding)
            Button("Import Library Bundle…") { model.importBundle(buildModel) }
                .help("Import a tile bundle: the tile's next build needs only your imagery")
                .disabled(buildModel.isBuilding)
            Button("Publish Patch…") { publishing = selectedRows.first }
                .help("Share one airport's solved patch of this tile in the patch library")
                .disabled(selectedRows.count != 1 || !writable || selectedRows.first?.airports.isEmpty != false
                          || buildModel.patchLibraryClient() == nil)
            Spacer()
            Text(model.status)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
    }

    private func setInstalled(_ install: Bool) {
        for row in selectedRows where row.inXPlane != install {
            buildModel.setInstalled(BuildModel.TileCoord(lat: row.lat, lon: row.lon), install)
        }
    }

    // MARK: - Disk

    private var diskPanel: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 4) {
            GridRow {
                Text("Tiles").bold()
                Text("\(Library.size(model.tilesBytes)) in \(model.tiles.count) tile\(model.tiles.count == 1 ? "" : "s")")
                    .monospacedDigit()
                Color.clear.frame(width: 1, height: 1)
            }
            ForEach(model.caches) { cache in
                GridRow {
                    Text(cache.label).bold()
                    Text(Library.size(cache.bytes)).monospacedDigit()
                    Button("Free Space…") { cacheToFree = cache }
                        .help(cache.redownload)
                        .disabled(buildModel.isBuilding || cache.bytes == 0)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
