import AppKit
import SwiftUI
import SceneryKit
import UniformTypeIdentifiers

/// The tiles table (#824; Library mode's from RULINGS 2026-11-10j until
/// 11k retired the mode). PARKED (owner 2026-11-11T15:35Z: the developer
/// tools of 11k (3) wait): no view shows it until its home is ruled; the
/// code stays. Every built tile with its size, zoom level, imagery source, built
/// date, graded airports, modified packs and the "In X-Plane" switch, and
/// the actions on the selection under it. The caches are Settings ▸
/// Storage's Caches line (`LibraryStorage.swift`). The engine's `library_*` commands
/// do the folder walks; the Qt app's `O4_Qt_Library` shows the same columns.
/// A tile built by another tool is read-only: it can be linked into
/// X-Plane or out of it, never rebuilt or deleted. Deleting and freeing
/// space ask first. Export / Import Library Bundle carry a built tile to
/// another installation (#1699 phase 1; the Qt dialog has the same two).
/// The "Patch library" section and "Publish Patch…" are the shared patch
/// library (#1699 phase 2, `PatchLibraryView.swift`), placed by its future home.
/// The table's selection IS the map's (one selection across modes).
enum Library {
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

/// The Library's rows (#2006): indexed once per scan (`LibraryIndex`);
/// the shown rows and the selection's rows are computed once per change
/// (tiles, search, sort, the map's selection), never per redraw.
@MainActor
final class LibraryModel: ObservableObject {
    @Published private(set) var index = LibraryIndex()
    @Published var tilesBytes: Int64 = 0
    @Published var isLoading = false
    @Published var status = ""
    @Published var search = "" { didSet { if search != oldValue { reshow() } } }
    @Published var sortOrder = [KeyPathComparator(\O4LibraryTile.tile)] { didSet { reshow() } }
    /// The rows the search keeps, sorted.
    @Published private(set) var shown: [O4LibraryTile] = []
    /// The map's selection as the table's rows (one selection, 10j).
    @Published private(set) var selectedIDs: Set<O4LibraryTile.ID> = []
    @Published private(set) var selectedRows: [O4LibraryTile] = []
    private var selectedCoords: Set<BuildModel.TileCoord> = []
    private var refreshAgain = false

    var tiles: [O4LibraryTile] { index.tiles }

    /// The map's selection changed.
    func select(_ coords: Set<BuildModel.TileCoord>) {
        selectedCoords = coords
        reselect()
    }

    /// The map's installed set changed (no folder walk).
    func applyInstalled(_ installed: Set<BuildModel.TileCoord>) {
        index.applyInstalled(installed)
        reshow()
        reselect()
    }

    /// Before the first `library_scan` answers: the tiles the map's scan
    /// already read, so the table is full at once (#2006).
    func seed(_ buildModel: BuildModel) {
        guard index.tiles.isEmpty, !buildModel.built.isEmpty else { return }
        setTiles(buildModel.built.keys.sorted().compactMap { coord in
            buildModel.built[coord].map {
                O4LibraryTile(mapTile: $0, inXPlane: buildModel.installed.contains(coord))
            }
        })
    }

    private func setTiles(_ tiles: [O4LibraryTile]) {
        index = LibraryIndex(tiles)
        reshow()
        reselect()
    }

    private func reshow() {
        shown = index.shown(query: search, sortOrder: sortOrder)
    }

    private func reselect() {
        let ids = index.ids(of: selectedCoords)
        if ids != selectedIDs { selectedIDs = ids }
        selectedRows = index.rows(ids)
    }

    /// One scan at a time: a refresh asked for while one runs runs once
    /// after it (the map's scan streams many changes).
    func refresh(_ buildModel: BuildModel) {
        guard let context = buildModel.libraryContext() else {
            status = "The engine is not running."
            return
        }
        guard !isLoading else {
            refreshAgain = true
            return
        }
        isLoading = true
        status = "Reading tiles…"
        Task {
            do {
                let scan = try await context.client.libraryScan(
                    workingDir: context.workingDir, sceneryDir: context.sceneryDir, caches: false)
                setTiles(scan.tiles)
                tilesBytes = scan.tilesBytes
                status = ""
            } catch {
                status = "\(error)"
            }
            isLoading = false
            if refreshAgain {
                refreshAgain = false
                refresh(buildModel)
            }
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

    /// "Always keep full resolution" / "Let it go low-res again" (#1992).
    func togglePin(_ row: O4LibraryTile, _ buildModel: BuildModel) {
        status = row.pinned == true ? "Removing from Favorites…" : "Adding to Favorites…"
        Task {
            status = await buildModel.setImageryPinned(
                BuildModel.TileCoord(lat: row.lat, lon: row.lon), row.pinned != true)
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

struct LibraryTilesSection: View {
    @EnvironmentObject private var buildModel: BuildModel
    /// `buildModel.library`: one model across mode switches.
    @ObservedObject var model: LibraryModel
    @State private var confirmDelete = false
    @State private var confirmRestore = false
    @State private var publishing: O4LibraryTile?

    private var selectedRows: [O4LibraryTile] { model.selectedRows }

    /// The map's selection, as the table's rows (one selection, 10j).
    private var selection: Binding<Set<O4LibraryTile.ID>> {
        Binding(
            get: { model.selectedIDs },
            set: { ids in
                let coords = model.index.coords(ids)
                buildModel.selected = Set(coords)
                if let first = coords.first, !coords.contains(where: { $0 == buildModel.activeTile }) {
                    buildModel.activeTile = first
                }
            })
    }

    private var selectedPacks: [O4LibraryPack] {
        Array(Set(selectedRows.flatMap(\.packsModified))).sorted { $0.packName < $1.packName }
    }

    private var writable: Bool {
        !selectedRows.isEmpty && !selectedRows.contains(where: \.readOnly)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                TextField("Search tiles, airports, imagery", text: $model.search)
                    .textFieldStyle(.roundedBorder)
                Text("\(Library.size(model.tilesBytes)) in \(model.tiles.count) tile\(model.tiles.count == 1 ? "" : "s")")
                    .monospacedDigit().foregroundStyle(.secondary)
                Button { model.refresh(buildModel) } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Read the tiles folder again")
                .disabled(model.isLoading)
            }
            table.frame(minHeight: 120)
            actions
            if !model.status.isEmpty {
                Text(model.status)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(8)
        .onAppear {
            model.seed(buildModel)
            model.select(buildModel.selected)
            model.refresh(buildModel)
        }
        .sheet(item: $publishing) { tile in PublishPatchSheet(tile: tile) }
        // Cheap per change (#2006): the selection and the In X-Plane
        // switches from the map; the folders are read again once the
        // map's scan is done.
        .onChange(of: buildModel.selected) { _, coords in model.select(coords) }
        .onChange(of: buildModel.installed) { _, installed in model.applyInstalled(installed) }
        .onChange(of: buildModel.isScanning) { _, scanning in
            if !scanning { model.refresh(buildModel) }
        }
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
        Table(model.shown, selection: selection, sortOrder: $model.sortOrder) {
            TableColumn("Tile", value: \.tile) { row in
                HStack(spacing: 4) {
                    Text(row.tile).monospacedDigit()
                        .foregroundStyle(row.readOnly ? .secondary : .primary)
                    if row.pinned == true {
                        // A favorite (#1992 §7, RULINGS 2026-11-10c (1)).
                        Image(systemName: "star.fill")
                            .foregroundStyle(.yellow)
                            .help(O4OnDemandText.pinnedState)
                            .accessibilityLabel(O4OnDemandText.pinnedBadge)
                    }
                }
            }
            TableColumn("Size", value: \.sizeBytes) { row in
                Text(row.detailsPending ? "…" : Library.size(row.sizeBytes)).monospacedDigit()
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
        // The tile's menu (#1992 §7): its pin (the Qt Library: the same).
        .contextMenu(forSelectionType: O4LibraryTile.ID.self) { ids in
            if ids.count == 1, let row = ids.first.flatMap(model.index.row),
               row.pinApplies {
                Button(pinTitle(row)) { model.togglePin(row, buildModel) }
                    .disabled(buildModel.isBuilding)
            }
        }
    }

    private func pinTitle(_ row: O4LibraryTile) -> String {
        row.pinned == true ? O4OnDemandText.unpinTitle : O4OnDemandText.pinTitle
    }

    /// The one selected tile a pin applies to.
    private var pinTarget: O4LibraryTile? {
        selectedRows.count == 1 && selectedRows[0].pinApplies ? selectedRows[0] : nil
    }

    // MARK: - Actions

    /// One row under the table (it spans the map's width).
    private var actions: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 120), alignment: .leading)],
                  alignment: .leading, spacing: 6) {
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
            Button(pinTarget.map(pinTitle) ?? O4OnDemandText.pinTitle) {
                if let row = pinTarget { model.togglePin(row, buildModel) }
            }
            .help(O4OnDemandText.pinHelp)
            .disabled(pinTarget == nil || buildModel.isBuilding)
        }
        .controlSize(.small)
    }

    private func setInstalled(_ install: Bool) {
        for row in selectedRows where row.inXPlane != install {
            buildModel.setInstalled(BuildModel.TileCoord(lat: row.lat, lon: row.lon), install)
        }
    }
}
