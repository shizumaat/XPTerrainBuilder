import AppKit
import SceneKit
import SceneryKit
import SwiftUI
import simd

/// An `SCNView` with the preview's camera (spec §5): drag orbits, scroll
/// or pinch zooms, ⌥-drag (or right-drag) pans over the ground, and
/// X-Plane's view keys move it (see `OrbitCamera`). Input moves a goal the
/// camera eases toward, so it never jumps. Read-only: no picking.
final class OrbitSCNView: SCNView {
    private let cameraNode = SCNNode()
    private var camera = OrbitCamera()
    private var held: Set<OrbitCamera.Key> = []
    private var speed: OrbitCamera.Speed = .normal
    private var ticker: Timer?
    private var lastTick: TimeInterval = 0
    var lastReset = -1

    func attach(_ scene: SCNScene) {
        self.scene = scene
        cameraNode.camera = SCNCamera()
        cameraNode.camera?.zNear = 1
        cameraNode.camera?.zFar = 200_000
        cameraNode.camera?.fieldOfView = 45
        scene.rootNode.addChildNode(cameraNode)
        pointOfView = cameraNode
        allowsCameraControl = false
        antialiasingMode = .multisampling4X
        backgroundColor = TerrainPreviewScene.background
    }

    /// Frame the ground extent from the south, looking north and down.
    func reset(center: SIMD3<Float>, radius: Float) {
        camera.reset(center: center, radius: radius)
        apply()
    }

    private func apply() {
        cameraNode.position = TerrainPreviewScene.vector(camera.eye)
        cameraNode.look(at: TerrainPreviewScene.vector(camera.shown.target))
    }

    /// Run the 60 Hz ease while a key is held or the camera has not
    /// reached its goal; stop when both are done.
    private func wake() {
        guard ticker == nil else { return }
        lastTick = ProcessInfo.processInfo.systemUptime
        let timer = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in
            self?.tick()
        }
        RunLoop.main.add(timer, forMode: .common)
        ticker = timer
    }

    private func tick() {
        let now = ProcessInfo.processInfo.systemUptime
        let dt = Float(min(now - lastTick, 0.1))
        lastTick = now
        camera.hold(held, speed: speed, dt: dt)
        let moving = camera.step(dt: dt)
        apply()
        if !moving && held.isEmpty {
            ticker?.invalidate()
            ticker = nil
        }
    }

    // MARK: Mouse

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
    }

    override func mouseDragged(with event: NSEvent) {
        if event.modifierFlags.contains(.option) { pan(event); return }
        camera.orbit(dx: Float(event.deltaX), dy: Float(event.deltaY))
        wake()
    }

    override func rightMouseDragged(with event: NSEvent) { pan(event) }

    private func pan(_ event: NSEvent) {
        camera.pan(dx: Float(event.deltaX), dy: Float(event.deltaY))
        wake()
    }

    override func scrollWheel(with event: NSEvent) {
        camera.scroll(Float(event.scrollingDeltaY), precise: event.hasPreciseScrollingDeltas)
        wake()
    }

    override func magnify(with event: NSEvent) {
        camera.magnify(Float(event.magnification))
        wake()
    }

    // MARK: Keys (X-Plane's view commands)

    override var acceptsFirstResponder: Bool { true }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        window?.makeFirstResponder(self)
    }

    /// X-Plane's default bindings, by key code so the keyboard layout's
    /// characters do not matter for the arrows.
    private static func key(for event: NSEvent) -> OrbitCamera.Key? {
        switch event.keyCode {
        case 123: return .left
        case 124: return .right
        case 126: return .up
        case 125: return .down
        default: break
        }
        switch event.charactersIgnoringModifiers?.lowercased() {
        case ".", ">": return .forward
        case ",", "<": return .backward
        case "=", "+": return .zoomIn
        case "-", "_": return .zoomOut
        case "q": return .rotateLeft
        case "e": return .rotateRight
        case "r": return .tiltUp
        case "f": return .tiltDown
        default: return nil
        }
    }

    private func readSpeed(_ flags: NSEvent.ModifierFlags) {
        speed = flags.contains(.shift) ? .fast : flags.contains(.control) ? .slow : .normal
    }

    override func keyDown(with event: NSEvent) {
        // ⌘ chords stay menu shortcuts (⌘W, ⌘3, ⌘Q…).
        guard !event.modifierFlags.contains(.command), let key = Self.key(for: event) else {
            super.keyDown(with: event)
            return
        }
        readSpeed(event.modifierFlags)
        held.insert(key)
        wake()
    }

    override func keyUp(with event: NSEvent) {
        guard let key = Self.key(for: event) else { super.keyUp(with: event); return }
        held.remove(key)
    }

    override func flagsChanged(with event: NSEvent) {
        readSpeed(event.modifierFlags)
        super.flagsChanged(with: event)
    }

    override func resignFirstResponder() -> Bool {
        held.removeAll()
        return super.resignFirstResponder()
    }
}

/// The SwiftUI host of the preview's scene.
struct TerrainSceneView: NSViewRepresentable {
    @ObservedObject var model: TerrainPreviewModel

    func makeNSView(context: Context) -> OrbitSCNView {
        let view = OrbitSCNView(frame: .zero)
        view.attach(model.scene.scene)
        return view
    }

    func updateNSView(_ view: OrbitSCNView, context: Context) {
        if view.lastReset != model.resetCount {
            view.lastReset = model.resetCount
            let e = model.scene.extent
            view.reset(center: e.center, radius: e.radius)
        }
    }
}
