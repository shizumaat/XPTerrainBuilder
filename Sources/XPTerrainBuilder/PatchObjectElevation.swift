import SwiftUI
import AppKit
import SceneryKit

// An object's elevation by hand, and a node snapped to an object (#1703;
// Qt's `O4_Qt_Object_Seat`):
//
// * "Set object elevation…" (the map's right-click menu and the Patch box,
//   with an object selected): the object's bottom in m MSL, stored at once
//   by the engine (`object_seat_set`) as a user edit the object stage
//   honours on every rebuild that places the airport's objects. Only the
//   object moves; the ground stays as solved (owner (1)(b)). One ⌘Z step.
// * A node dropped on an object's footprint corner or edge middle (the
//   drag snap, `PatchEditGestures.swift`) is asked, when the object has a
//   height, whether it takes the object's top or bottom elevation (owner
//   (2)(a), (4)(a)): "Top", "Bottom", "Keep current". The node's `alt_abs`
//   then pins it, and the build grades to it.

extension PatchObjectInspector {
    static let setElevationTitle = "Set object elevation…"

    /// Whether "Set object elevation…" is offered: an object is selected and
    /// the engine has `object_seat_set`.
    var canSetElevation: Bool {
        guard selected?.object != nil, let build = patch?.build else { return false }
        return O4ProtocolVersion.supportsObjectSeatSet(build.protocolHello?.protocolVersion ?? "")
    }

    /// Store the selected object's bottom (m MSL); nil: back to the object
    /// stage's own seat. ONE undo step.
    func setElevation(bottomM: Double?) {
        guard let object = selected?.object, let doc = patch?.document,
              let client = patch?.build?.patchEditorClient() else { return }
        let name = bottomM == nil ? "Clear Object Elevation" : "Set Object Elevation"
        Task { @MainActor [weak self] in
            do {
                let reply = try await client.objectSeatSet(tile: doc.tile, icao: doc.icao, object: object,
                                                           bottomM: bottomM)
                guard let self else { return }
                self.stored(object, tile: doc.tile)
                self.registerUndo(object, tile: doc.tile, icao: doc.icao, to: reply.previousZeroM,
                                  back: reply.zeroM, name: name)
            } catch {
                self?.patch?.editError = "The object's elevation could not be set: \(error)"
            }
        }
    }

    /// Undo / redo: send `to`, and register the way back (synchronously, so
    /// the undo manager files it as the redo).
    private func registerUndo(_ object: PackObjectRef, tile: String, icao: String, to: Double?, back: Double?,
                              name: String) {
        guard let patch, let undo = patch.undoManager else { return }
        undo.registerUndo(withTarget: patch) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.registerUndo(object, tile: tile, icao: icao, to: back, back: to, name: name)
                self.send(object, tile: tile, icao: icao, zeroM: to)
            }
        }
        undo.setActionName(name)
    }

    private func send(_ object: PackObjectRef, tile: String, icao: String, zeroM: Double?) {
        guard let client = patch?.build?.patchEditorClient() else { return }
        Task { @MainActor [weak self] in
            do {
                _ = try await client.objectSeatSet(tile: tile, icao: icao, object: object, zeroM: zeroM)
                self?.stored(object, tile: tile)
            } catch {
                self?.patch?.editError = "The object's elevation could not be set: \(error)"
            }
        }
    }

    /// After a write: the tile wants a rebuild; the inspector reads again.
    private func stored(_ object: PackObjectRef, tile: String) {
        patch?.tilesNeedingRebuild.insert(tile)
        if selected?.object == object { ask(object) }
    }

    /// A node dropped on `object`'s snap point: when the object has a height,
    /// ask (at the pointer) whether the node takes its top or bottom.
    func offerTopOrBottom(node: Int64, object: PackObjectRef) {
        guard let patch, let doc = patch.document, let build = patch.build,
              let client = build.patchEditorClient() else { return }
        let at = NSEvent.mouseLocation
        let buildDir = Self.buildDir(object, build: build)
        Task { @MainActor [weak patch] in
            for _ in 0..<20 {
                guard let seat = try? await client.objectSeat(tile: doc.tile, icao: doc.icao, object: object,
                                                              buildDir: buildDir) else { return }
                if seat.pending {
                    try? await Task.sleep(nanoseconds: 400_000_000)
                    continue
                }
                guard seat.hasHeight, let top = seat.topM, let bottom = seat.bottomM, let patch,
                      patch.document?.nodes[node] != nil else { return }
                PatchTopOrBottomMenu(top: top, bottom: bottom) { alt, title in
                    patch.perform(title) { try $0.setAlt([node], alt: alt) }
                }.show(at: at)
                return
            }
        }
    }
}

/// The snap's small pop-up: Top / Bottom / Keep current (Qt: a `QMenu`).
@MainActor
private final class PatchTopOrBottomMenu: NSObject {
    private let top: Double
    private let bottom: Double
    private let choose: (Double, String) -> Void

    init(top: Double, bottom: Double, choose: @escaping (Double, String) -> Void) {
        self.top = top
        self.bottom = bottom
        self.choose = choose
    }

    func show(at point: NSPoint) {
        let menu = NSMenu()
        menu.autoenablesItems = false
        let heading = NSMenuItem(title: "Node elevation", action: nil, keyEquivalent: "")
        heading.isEnabled = false
        menu.addItem(heading)
        for (title, sel) in [(String(format: "Top of the object (%.2f m)", top), #selector(takeTop)),
                             (String(format: "Bottom of the object (%.2f m)", bottom), #selector(takeBottom)),
                             ("Keep current", #selector(keep))] {
            let item = NSMenuItem(title: title, action: sel, keyEquivalent: "")
            item.target = self
            menu.addItem(item)
        }
        menu.popUp(positioning: nil, at: point, in: nil)
    }

    @objc private func takeTop() { choose(top, "Set Elevation to Object Top") }
    @objc private func takeBottom() { choose(bottom, "Set Elevation to Object Bottom") }
    @objc private func keep() {}
}

/// "Set object elevation…": the object's bottom in m or ft, prefilled with
/// the seat the inspector shows; "Automatic" drops a hand-set elevation.
struct PatchObjectElevationSheet: View {
    @ObservedObject var inspector: PatchObjectInspector
    @State private var text = ""
    @State private var unit: PatchShapeElevation.Unit = .metres

    init(inspector: PatchObjectInspector) {
        self.inspector = inspector
        _text = State(initialValue: Self.format(inspector.seat?.bottomM, in: .metres))
    }

    var body: some View {
        let seat = inspector.seat
        VStack(alignment: .leading, spacing: 10) {
            Text(inspector.selected?.label ?? "Object").scaledFont(.callout, weight: .semibold)
            Text("Only the object moves; the ground stays as built. It is placed there on the next rebuild.")
                .scaledFont(.callout).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 6) {
                Text("Bottom").foregroundStyle(.secondary)
                TextField("", text: $text)
                    .textFieldStyle(.roundedBorder)
                    .scaledFont(.callout, monospacedDigit: true)
                    .frame(width: 110)
                    .onSubmit(apply)
                Picker("", selection: $unit) {
                    ForEach(PatchShapeElevation.Unit.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(width: 80)
                Text("MSL").foregroundStyle(.secondary)
            }
            if let h = seat?.heightM {
                Text(String(format: "Its top is %.2f m above its bottom.", h)).foregroundStyle(.secondary)
            }
            HStack {
                if seat?.userZeroM != nil {
                    Button("Automatic") {
                        inspector.setElevation(bottomM: nil)
                        inspector.showsSetElevation = false
                    }
                    .help("Let the build seat the object again")
                }
                Spacer()
                Button("Cancel", role: .cancel) { inspector.showsSetElevation = false }
                    .keyboardShortcut(.cancelAction)
                Button("Apply", action: apply)
                    .keyboardShortcut(.defaultAction)
                    .disabled(PatchNodeInspector.number(text) == nil)
            }
        }
        .padding(20)
        .frame(width: 380)
        .onChange(of: unit) { old, new in
            let metres = PatchNodeInspector.number(text).map { PatchShapeElevation.metres($0, from: old) }
            text = Self.format(metres, in: new)
        }
    }

    private func apply() {
        guard let v = PatchNodeInspector.number(text) else { return }
        inspector.setElevation(bottomM: PatchShapeElevation.metres(v, from: unit))
        inspector.showsSetElevation = false
    }

    private static func format(_ metres: Double?, in unit: PatchShapeElevation.Unit) -> String {
        metres.map { String(format: "%.2f", PatchShapeElevation.value($0, in: unit)) } ?? ""
    }
}

/// The Patch box in Edit mode with an object selected: its name, the
/// inspector's lines and "Set object elevation…".
struct PatchObjectBox: View {
    @ObservedObject var inspector: PatchObjectInspector

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(inspector.lines.enumerated()), id: \.offset) { k, line in
                Text(line).scaledFont(.callout, weight: k == 0 ? .semibold : .regular)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if inspector.canSetElevation {
                Button(PatchObjectInspector.setElevationTitle) { inspector.showsSetElevation = true }
                    .disabled(inspector.seat == nil)
                    .help("Set where this object stands; only the object moves")
            }
        }
    }
}

/// Where "Set object elevation…" opens: on the map, so the right-click
/// menu reaches it with the side panel closed.
struct PatchObjectElevationHost: View {
    @ObservedObject var inspector: PatchObjectInspector

    var body: some View {
        Color.clear.allowsHitTesting(false)
            .sheet(isPresented: $inspector.showsSetElevation) { PatchObjectElevationSheet(inspector: inspector) }
    }
}
