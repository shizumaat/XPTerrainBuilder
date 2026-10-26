import AppKit
import SceneryKit

/// Edit mode's actions on the patch document (patch-editor spec §3, §4):
/// each edit is ONE undo step on the window's `UndoManager`, and every
/// edit, undo and redo ends in `documentChanged(_:)` with exactly what it
/// touched. Saving and reverting go through the engine (`patch_save`,
/// `patch_revert`); the unsaved-edits prompt guards an airport switch and
/// quitting.
extension PatchEditModel {

    // MARK: - Edits

    /// Apply one edit as one undo step named `name`. A refused edit (the
    /// §3 ops throw on unknown ids or a non-edge) changes nothing.
    @discardableResult
    func perform(_ name: String, _ edit: (inout PatchDocument) throws -> Void) -> Bool {
        guard let before = document else { return false }
        var after = before
        do {
            try edit(&after)
        } catch {
            editError = "\(error)"
            return false
        }
        let step = PatchEditStep(from: before, to: after)
        guard !step.isEmpty else { return false }
        editError = nil
        document = after
        if savedReachable, undoLevel < savedLevel { savedReachable = false } // branched below the save
        undoLevel += 1
        registerInverse(of: step, name: name, applied: false)
        finish(step)
        return true
    }

    /// Move the selection by (dlat, dlon); `merge` = the snap held at
    /// release: the grabbed node then merges into its target (§3.3).
    func moveSelection(_ ids: [Int64], dlat: Double, dlon: Double, merge: (source: Int64, target: Int64)?) {
        let name = merge != nil ? "Move and Merge" : shapeSelection.isEmpty ? "Move"
            : shapeSelection.count == 1 ? "Move Shape" : "Move Shapes"
        let done = perform(name) { doc in
            try doc.move(ids, dlat: dlat, dlon: dlon)
            if let merge { try doc.mergeNodes(source: merge.source, target: merge.target) }
        }
        if done, let merge {
            selection.remove(merge.source)
            selection.insert(merge.target)
        }
    }

    /// The "+" handle on edge a–b: the new node becomes the selection.
    func insertNode(_ a: Int64, _ b: Int64) {
        var newID: Int64?
        if perform("Insert Node", { newID = try $0.insertOnEdge(a, b) }), let newID {
            selectShapes([])
            selection = [newID]
        }
    }

    func setSelectionAlt(_ alt: Double) {
        let ids = selection.sorted()
        perform("Set Elevation") { try $0.setAlt(ids, alt: alt) }
    }

    func offsetSelectionAlt(_ d: Double) {
        let ids = selection.sorted()
        perform("Offset Elevation") { try $0.offsetAlt(ids, by: d) }
    }

    // MARK: - Undo / redo

    /// Register the step's inverse; run as an undo it registers the redo.
    private func registerInverse(of step: PatchEditStep, name: String, applied reversed: Bool) {
        guard let undoManager else { return }
        let generation = documentGeneration
        undoManager.registerUndo(withTarget: self) { model in
            MainActor.assumeIsolated {
                model.replay(step, name: name, reversed: !reversed, generation: generation)
            }
        }
        undoManager.setActionName(name)
    }

    private func replay(_ step: PatchEditStep, name: String, reversed: Bool, generation: Int) {
        guard generation == documentGeneration, var doc = document else { return }
        doc.apply(step, reversed: reversed)
        document = doc
        undoLevel += reversed ? -1 : 1
        registerInverse(of: step, name: name, applied: reversed)
        finish(step)
    }

    /// After an edit, undo or redo: drop vanished nodes from the selection,
    /// recount, and announce the change.
    private func finish(_ step: PatchEditStep) {
        if let doc = document {
            let gone = selection.filter { doc.nodes[$0] == nil }
            if !gone.isEmpty { selection.subtract(gone) }
        }
        dropVanishedShapes()
        recountUnsaved()
        documentChanged(PatchChange(nodes: step.movedNodes, ways: step.changedWays, topology: step.topology))
    }

    func recountUnsaved() {
        let distance = abs(undoLevel - savedLevel)
        unsavedEdits = savedReachable ? distance : max(1, distance)
    }

    /// A new document (load, reload, revert): history and counters restart.
    func documentLoaded() {
        documentGeneration += 1
        undoManager?.removeAllActions(withTarget: self)
        undoLevel = 0
        savedLevel = 0
        savedReachable = true
        unsavedEdits = 0
        editError = nil
        dismissedSwitchKey = nil
        loadedNodes = document?.nodes ?? [:]
    }

    // MARK: - Save / revert

    /// `patch_save` with the full document; the document then IS the saved
    /// manual patch (history kept). Returns whether it saved.
    @discardableResult
    func save() async -> Bool {
        guard let doc = document, !isSaving else { return false }
        guard let client = build?.patchEditorClient() else {
            editError = "The engine is not running, so the patch cannot be saved."
            return false
        }
        isSaving = true
        defer { isSaving = false }
        let level = undoLevel
        let rows = doc.saveRows
        do {
            let reply = try await client.patchSave(tile: doc.tile, icao: doc.icao, basePath: doc.path,
                                                   nodes: rows.nodes, ways: rows.ways)
            guard var current = document, current.tile == doc.tile, current.icao == doc.icao else { return false }
            current.markSaved(path: reply.path)
            document = current
            savedLevel = level
            savedReachable = true
            recountUnsaved()
            editError = nil
            tilesNeedingRebuild.insert(doc.tile)
            fileDate = (try? FileManager.default.attributesOfItem(atPath: reply.path))?[.modificationDate] as? Date
            if let coord = Self.coord(doc.tile), let entries = listings[coord]?.entries {
                listings[coord]?.entries = entries.map { $0.icao == doc.icao ? $0.savedAs(path: reply.path) : $0 }
            }
            return true
        } catch {
            editError = "\(error)"
            return false
        }
    }

    /// "Revert to auto…": the editor's own file is moved aside
    /// (`patch_revert`, never deleted) and the auto patch reloads; on an
    /// auto patch it discards the unsaved edits.
    func revertToAuto() async {
        guard let doc = document, !doc.isHandMade else { return }
        if doc.source == .manual {
            guard let client = build?.patchEditorClient() else {
                editError = "The engine is not running, so the patch cannot be reverted."
                return
            }
            do {
                _ = try await client.patchRevert(tile: doc.tile, icao: doc.icao)
            } catch {
                editError = "\(error)"
                return
            }
            tilesNeedingRebuild.insert(doc.tile)
            if let coord = Self.coord(doc.tile) { listings[coord] = nil } // list the tile again
        }
        discardEdits()
    }

    /// Forget the unsaved edits and load the airport's file again.
    func discardEdits() {
        unsavedEdits = 0
        savedReachable = true
        undoLevel = savedLevel
        reloadDocument = true
        scheduleEvaluate()
    }

    // MARK: - Rebuild

    /// "Rebuild tile": the Build box's own path — select the tile, build
    /// it with the source and zoom it was built with.
    func rebuildTile() {
        guard let build, let doc = document, let coord = Self.coord(doc.tile) else { return }
        build.click(lat: coord.lat, lon: coord.lon, command: false, shift: false)
        guard build.canBuild else {
            editError = build.xplaneBlockReason
                ?? "This tile can't be rebuilt now. Turn off “Skip already-built tiles” and try again."
            return
        }
        let choice = build.built[coord].flatMap(TileImageryChoice.resolve)
        build.startBuild(batches: [([coord], choice?.provider ?? build.buildProvider,
                                    choice?.zl ?? build.buildZL)])
    }

    // MARK: - Unsaved-edits prompt

    /// Whether a switch to `key` must wait for the user (unsaved edits).
    func holdForUnsavedEdits(switchingTo icao: String, key: String) -> Bool {
        guard document != nil, unsavedEdits > 0 else { return false }
        if dismissedSwitchKey != key, prompt != .quit { prompt = .switchAirport(icao: icao, key: key) }
        return true
    }

    func answerPrompt(save: Bool?, discard: Bool = false) {
        guard let asked = prompt else { return }
        Task {
            if save == true, !(await self.save()) { return } // the error shows; the prompt stays
            if discard { self.unsavedEdits = 0; self.savedReachable = true; self.undoLevel = self.savedLevel }
            let proceed = save == true || discard
            self.prompt = nil
            switch asked {
            case .quit:
                NSApp.reply(toApplicationShouldTerminate: proceed)
            case .switchAirport(_, let key):
                if !proceed { self.dismissedSwitchKey = key }
                self.scheduleEvaluate()
            }
        }
    }

    /// The app delegate's quit check: unsaved edits ask in the map first.
    func shouldTerminate() -> NSApplication.TerminateReply {
        guard document != nil, unsavedEdits > 0 else { return .terminateNow }
        prompt = .quit
        return .terminateLater
    }

    static func coord(_ tile: String) -> BuildModel.TileCoord? {
        TileMath.parse(tile).map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) }
    }
}
