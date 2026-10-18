import SwiftUI
import SceneryKit

/// The "Patch · ICAO" box in `BuildPane`, below Activity (patch-editor
/// spec §4; mockup side panel). View mode: the source line, counts, the
/// stale note, and "Build this tile first" when the zoomed airport has no
/// patch. Edit mode adds the node inspector (`PatchNodeInspector`); the
/// save bar (`PatchSaveBar`) shows in Edit mode and whenever there is
/// something to save or rebuild. Renders nothing while the layer is hidden.
struct PatchInspector: View {
    @ObservedObject var model: PatchEditModel

    var body: some View {
        if let icao = title {
            GroupBox {
                VStack(alignment: .leading, spacing: 8) { content }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(4)
            } label: {
                Text("\(O4Glossary.term("ground_shape")) · \(icao)").font(.callout.weight(.semibold))
            }
        }
    }

    private var title: String? {
        switch model.state {
        case .hidden: return nil
        case .loading(let icao), .failed(let icao, _), .noPatch(let icao, _): return icao
        case .loaded: return model.document?.icao
        }
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .hidden:
            EmptyView()
        case .loading:
            HStack(spacing: 6) {
                ProgressView().controlSize(.small)
                Text("Loading the ground shape…").foregroundStyle(.secondary)
            }
        case .failed(_, let message):
            Text(message).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
        case .noPatch(_, let tileBuilt):
            Text(tileBuilt ? "No ground shape was built for this airport." : "Build this tile first.")
                .foregroundStyle(.secondary)
        case .loaded:
            if let doc = model.document { loaded(doc) }
        }
    }

    @ViewBuilder
    private func loaded(_ doc: PatchDocument) -> some View {
        row("Source", sourceLine(doc))
        row("Shapes", "\(doc.nodes.count.formatted()) nodes · \(doc.ways.count.formatted()) shapes")
        let meshNodes = doc.nodesWithoutElevation
        if meshNodes > 0 {
            note("\(meshNodes.formatted()) nodes: elevation from the mesh.")
        }
        if doc.stale {
            note("The engine, elevation or airport data has changed since this ground shape was edited. The automatic shape would now be different, but your edited shape is still used.",
                 color: MapCanvasView.badgeStopped)
                .help(doc.staleInputs.joined(separator: ", "))
        }
        if model.mode == .edit {
            Divider()
            if model.shapeSelection.isEmpty {
                PatchNodeInspector(model: model, doc: doc)
            } else {
                PatchShapeInspector(model: model, doc: doc)
            }
        }
        if model.mode == .edit || model.unsavedEdits > 0 || model.tilesNeedingRebuild.contains(doc.tile)
            || model.editError != nil {
            Divider()
            PatchSaveBar(model: model, doc: doc)
        }
    }

    /// "Automatic, built 12 Oct" / "Edited · KHIO_edited.patch.osm" /
    /// "Manual · KHIO_runways.patch.osm".
    private func sourceLine(_ doc: PatchDocument) -> String {
        let file = (doc.path as NSString).lastPathComponent
        switch doc.source {
        case .auto:
            guard let date = model.fileDate else { return "Automatic" }
            return "Automatic, built \(date.formatted(.dateTime.day().month(.abbreviated)))"
        case .manual:
            return doc.isHandMade ? "Manual · \(file)" : "Edited · \(file)"
        }
    }

    private func row(_ key: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(key).foregroundStyle(.secondary)
            Spacer(minLength: 8)
            Text(value).multilineTextAlignment(.trailing).textSelection(.enabled)
        }
        .font(.callout)
    }

    private func note(_ text: String, color: Color = .secondary) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(color)
            .fixedSize(horizontal: false, vertical: true)
    }
}
