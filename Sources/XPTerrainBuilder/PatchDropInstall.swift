import SwiftUI
import SceneryKit
import UniformTypeIdentifiers

/// Patches dropped on the map or opened on the app icon (#1979; Qt:
/// `O4_Qt_Patch_Drop.py`). The engine says what was dropped and where it
/// goes (`patch_drop_plan`); the map asks with that plan's summary and
/// installs on "Install" (`patch_drop_install`).
///
/// A `.xptb` package dropped or opened the same ways goes to the package
/// install instead (#2014, `TilePackageSheets.swift`).
///
/// Files opened on the Dock icon or with Finder's "Open With" arrive in
/// `AppDelegate.application(_:open:)`, possibly before the map exists;
/// they wait in `PatchDropInbox` until the map's `PatchDropTarget` takes them.
@MainActor
final class PatchDropInbox: ObservableObject {
    static let shared = PatchDropInbox()
    @Published private(set) var pending: [URL] = []

    func receive(_ urls: [URL]) { pending += urls.filter(\.isFileURL) }

    func take() -> [URL] {
        defer { pending = [] }
        return pending
    }
}

/// One drop's state: the plan awaiting "Install", or the sentence that
/// refused it.
@MainActor
final class PatchDropModel: ObservableObject {
    struct Prompt: Identifiable {
        let id = UUID()
        let paths: [String]
        let plan: O4PatchDropPlan
    }

    @Published var prompt: Prompt?
    @Published var refusal: String?

    func offer(_ urls: [URL], build: BuildModel) {
        let paths = urls.map(\.path)
        guard !paths.isEmpty, let client = build.libraryContext()?.client else { return }
        let caps = build.engineCapabilities
        if !caps.protocolVersion.isEmpty && !caps.supports(O4EngineCapabilities.patchDrop) {
            refusal = "This build engine cannot install dropped patches."
            return
        }
        Task { [weak self] in
            do {
                let plan = try await client.patchDropPlan(paths: paths)
                let busy = plan.tiles.filter { key in
                    guard let t = TileMath.parse(key) else { return false }
                    return build.tileInRun(BuildModel.TileCoord(lat: t.lat, lon: t.lon))
                }
                if busy.isEmpty {
                    self?.prompt = Prompt(paths: paths, plan: plan)
                } else {
                    self?.refusal = O4PatchDropCopy.building(busy)
                }
            } catch {
                self?.refusal = error.localizedDescription
            }
        }
    }

    func install(_ prompt: Prompt, build: BuildModel) {
        guard let client = build.libraryContext()?.client else { return }
        Task { [weak self] in
            do {
                let done = try await client.patchDropInstall(paths: prompt.paths)
                for item in done.items {
                    build.console.append(O4PatchDropCopy.installed(item), tile: item.tile)
                }
            } catch {
                self?.refusal = error.localizedDescription
            }
            build.refreshCustomPatchTiles()
        }
    }
}

/// The map's drop hook: file drops, the Dock icon's inbox, and the
/// confirmation and refusal alerts.
struct PatchDropTarget: ViewModifier {
    @ObservedObject var buildModel: BuildModel
    @StateObject private var model = PatchDropModel()
    @ObservedObject private var inbox = PatchDropInbox.shared

    func body(content: Content) -> some View {
        content
            .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                Task { @MainActor in route(await Self.urls(providers)) }
                return true
            }
            .onChange(of: inbox.pending) { _, urls in
                if !urls.isEmpty { route(inbox.take()) }
            }
            .onAppear {
                if !inbox.pending.isEmpty { route(inbox.take()) }
            }
            .modifier(TilePackageSheets(buildModel: buildModel))
            .alert(O4PatchDropCopy.title, isPresented: Binding(
                get: { model.prompt != nil },
                set: { if !$0 { model.prompt = nil } }
            ), presenting: model.prompt) { prompt in
                Button(O4PatchDropCopy.install) { model.install(prompt, build: buildModel) }
                Button("Cancel", role: .cancel) {}
            } message: { prompt in
                Text(prompt.plan.summary.joined(separator: "\n"))
            }
            .alert(O4PatchDropCopy.title, isPresented: Binding(
                get: { model.refusal != nil },
                set: { if !$0 { model.refusal = nil } }
            )) {
                Button("OK") { model.refusal = nil }
            } message: {
                Text(model.refusal ?? "")
            }
    }

    /// A `.xptb` package goes to the package install (#2014,
    /// `TilePackageSheets.swift`); anything else is a patch drop.
    private func route(_ urls: [URL]) {
        let packages = urls.filter(O4TilePackage.isPackage)
        if !packages.isEmpty { TilePackageModel.shared.offer(packages, build: buildModel) }
        let rest = urls.filter { !O4TilePackage.isPackage($0) }
        if !rest.isEmpty { model.offer(rest, build: buildModel) }
    }

    /// The file URLs the drag carries.
    static func urls(_ providers: [NSItemProvider]) async -> [URL] {
        var out: [URL] = []
        for provider in providers {
            let item = try? await provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier)
            if let data = item as? Data, let url = URL(dataRepresentation: data, relativeTo: nil) {
                out.append(url)
            } else if let url = item as? URL {
                out.append(url)
            }
        }
        return out
    }
}
