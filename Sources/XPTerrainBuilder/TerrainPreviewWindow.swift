import SwiftUI
import SceneryKit

/// The 3D preview window (patch-editor spec §5, A8; mockup
/// `Ortho4XP/docs/mockups/patch-editor-20261015.html` "3D preview"):
/// terrain with the patch applied, live while editing, read-only. Round 6a:
/// Preview only — Imagery, Buildings and "Last build" come in 6b/6c.
enum TerrainPreview {
    static let windowID = "terrain-preview"
    /// One window: `openWindow(id:value:)` with a fixed value brings the
    /// open one forward instead of opening another.
    static let windowValue = "preview"
}

struct TerrainPreviewWindow: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        TerrainPreviewContent(build: buildModel)
    }
}

private struct TerrainPreviewContent: View {
    @StateObject private var model: TerrainPreviewModel

    init(build: BuildModel) {
        _model = StateObject(wrappedValue: TerrainPreviewModel(patch: build.patchEdit, build: build))
    }

    var body: some View {
        ZStack {
            TerrainSceneView(model: model)
            statusMessage
        }
        .overlay(alignment: .topLeading) { toolbar }
        .overlay(alignment: .topTrailing) { legend }
        .overlay(alignment: .bottomLeading) { chip }
        .overlay(alignment: .bottomTrailing) { resetButton }
        .frame(minWidth: 560, minHeight: 360)
        .background(Color(nsColor: TerrainPreviewScene.background))
        .navigationTitle(model.icao.map { "3D Preview · \($0)" } ?? "3D Preview")
    }

    @ViewBuilder private var statusMessage: some View {
        switch model.status {
        case .noPatch:
            Text("Zoom the map in on a built airport to preview its patch in 3D.")
                .foregroundStyle(.secondary)
        case .loading(let icao):
            ProgressView("Reading the terrain under \(icao)…")
                .controlSize(.small)
        case .ready:
            EmptyView()
        }
    }

    private var modeBinding: Binding<PatchLastBuildState.Mode> {
        Binding(get: { model.lastBuildState.mode }, set: { model.selectMode($0) })
    }

    private var toolbar: some View {
        HStack(spacing: 10) {
            Picker("", selection: modeBinding) {
                Text("Preview").tag(PatchLastBuildState.Mode.preview)
                Text("Last build").tag(PatchLastBuildState.Mode.lastBuild)
                    .disabled(!model.lastBuildState.canShowLastBuild)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .fixedSize()
            .help(model.lastBuildState.unavailableReason
                  ?? "Preview follows your edits; Last build is the mesh X-Plane loads, refreshed after a rebuild.")
            Divider().frame(height: 16)
            Toggle("Imagery", isOn: $model.showImagery)
                .toggleStyle(.checkbox)
                .help("Drape the map's imagery over the ground (the tiles the map has cached).")
            Toggle("Buildings", isOn: $model.showBuildings)
                .toggleStyle(.checkbox)
                .help("The airport pack's buildings as grey massing, standing where X-Plane seats them.")
            Toggle("Wireframe", isOn: $model.wireframe)
                .toggleStyle(.checkbox)
            Divider().frame(height: 16)
            Text("Vertical ×")
                .foregroundStyle(.secondary)
            Text(String(format: "%.1f", model.exaggeration))
                .font(.system(.body, design: .monospaced))
                .frame(width: 34, alignment: .trailing)
            Slider(value: $model.exaggeration, in: 1...10)
                .frame(width: 110)
                .help("Vertical exaggeration of the terrain and the patch (×1 is true scale).")
        }
        .font(.callout)
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 8))
        .padding(10)
    }

    private var legend: some View {
        VStack(alignment: .leading, spacing: 3) {
            legendRow(TerrainPreviewScene.terrainColor, "DEM terrain")
            legendRow(TerrainPreviewScene.patchColor, "patch surface")
            legendRow(TerrainPreviewScene.buildingColor, "pack buildings")
            legendRow(TerrainPreviewScene.markerColor, "selected node")
        }
        .font(.caption)
        .foregroundStyle(.white.opacity(0.85))
        .padding(.horizontal, 9).padding(.vertical, 6)
        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 8))
        .padding(10)
    }

    private func legendRow(_ color: NSColor, _ label: String) -> some View {
        HStack(spacing: 6) {
            RoundedRectangle(cornerRadius: 2).fill(Color(nsColor: color)).frame(width: 14, height: 8)
            Text(label)
        }
    }

    @ViewBuilder private var chip: some View {
        let error: String? = {
            if case .ready(let e) = model.status { return e }
            return nil
        }()
        if !model.chip.isEmpty || error != nil {
            VStack(alignment: .leading, spacing: 4) {
                if let error {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                        .lineLimit(3)
                }
                if !model.chip.isEmpty {
                    Text(model.chip + buildingsChip + model.drapeChip + model.lastBuildChip)
                }
                if case .loading = model.lastBuildState.mesh {
                    Text("Reading the last build's mesh…")
                }
                if case .failed(let text) = model.buildingStatus {
                    Label(text, systemImage: "building.2").foregroundStyle(.orange).lineLimit(3)
                }
            }
            .font(.system(size: 11, design: .monospaced))
            .foregroundStyle(.white.opacity(0.75))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 6))
            .frame(maxWidth: 520, alignment: .leading)
            .help(buildingsNotes)
            .padding(10)
        }
    }

    /// " · 142 pack objects" / " · loading buildings…".
    private var buildingsChip: String {
        switch model.buildingStatus {
        case .loading: return " · Loading buildings…"
        case .ready(let n, _): return " · \(n.formatted()) pack objects"
        case .none, .failed: return ""
        }
    }

    /// What the engine could not show (`pack_objects` `missing`), on hover.
    private var buildingsNotes: String {
        if case .ready(_, let missing) = model.buildingStatus { return missing.joined(separator: "\n") }
        return ""
    }

    /// The camera controls, X-Plane's view keys first (OrbitCamera).
    static let controlsHelp = """
        Keys (as in X-Plane): Q E rotate · R F tilt · ← → move sideways ·         ↑ ↓ move up and down · , . move back and forward · - = zoom.         Hold Shift for fast, Control for slow.
        Mouse: drag to orbit · ⌥-drag or right-drag to pan · scroll or pinch to zoom.
        """

    private var resetButton: some View {
        HStack(spacing: 6) {
            Image(systemName: "keyboard")
                .foregroundStyle(.secondary)
                .help(Self.controlsHelp)
            Button { model.resetView() } label: {
                Label("Reset view", systemImage: "arrow.counterclockwise")
            }
            .buttonStyle(.borderless)
            .help("Frame the airport again from the south.")
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 6))
        .padding(10)
    }
}

/// The map's "3D" button (top-left of the map): shown while a patch layer
/// is in play, enabled once the patch is drawn.
struct TerrainPreviewButton: View {
    @ObservedObject var model: PatchEditModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        if model.state != .hidden {
            Button {
                openWindow(id: TerrainPreview.windowID, value: TerrainPreview.windowValue)
            } label: {
                Text("3D").fontWeight(.semibold).frame(width: 30, height: 22)
            }
            .buttonStyle(.borderless)
            .disabled(!model.isShowing)
            .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
            .padding(8)
            .help("Open the 3D preview of this airport's patch (⌘3).")
        }
    }
}
