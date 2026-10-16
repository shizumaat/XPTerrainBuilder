import AppKit
import SceneKit
import SceneryKit
import SwiftUI
import simd

/// An `SCNView` with the preview's free-look camera (spec §5, #794): the
/// scene is fixed and the eye looks around — drag turns the view, scroll
/// or pinch moves along it, ⌥-drag (or right-drag) moves the eye over the
/// ground, X-Plane's view keys move and turn it, Home or 0 returns to the
/// first view (see `FreeLookCamera`). Input moves a goal the camera eases
/// toward, so it never jumps. Read-only: no picking.
final class FreeLookSCNView: SCNView {
    private let cameraNode = SCNNode()
    private var camera = FreeLookCamera()
    private var held: Set<FreeLookCamera.Key> = []
    private var speed: FreeLookCamera.Speed = .normal
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

    /// The first view: above and south of the extent, aimed at its centre.
    func reset(center: SIMD3<Float>, radius: Float) {
        camera.reset(center: center, radius: radius)
        apply()
    }

    /// The terrain under the eye (it changes with the exaggeration); the
    /// eye is lifted out if the ground rose through it.
    func setGround(_ ground: ((Float, Float) -> Float?)?) {
        camera.ground = ground
        if let g = camera.groundY(under: camera.shown.eye),
           camera.shown.eye.y < g + FreeLookCamera.minClearance {
            wake()
        }
    }

    private func apply() {
        let eye = camera.shown.eye
        cameraNode.simdPosition = eye
        cameraNode.simdLook(at: eye + camera.lookDirection, up: SIMD3(0, 1, 0), localFront: SIMD3(0, 0, -1))
        cameraNode.camera?.fieldOfView = CGFloat(camera.shown.fov)
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
        if event.modifierFlags.contains(.option) { move(event); return }
        camera.look(dx: Float(event.deltaX), dy: Float(event.deltaY))
        wake()
    }

    override func rightMouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
    }

    override func rightMouseDragged(with event: NSEvent) { move(event) }

    private func move(_ event: NSEvent) {
        camera.move(dx: Float(event.deltaX), dy: Float(event.deltaY))
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
    private static func key(for event: NSEvent) -> FreeLookCamera.Key? {
        switch event.keyCode {
        case 123: return .left
        case 124: return .right
        case 126: return .forward
        case 125: return .backward
        default: break
        }
        switch event.charactersIgnoringModifiers?.lowercased() {
        case ".", ">": return .viewForward
        case ",", "<": return .viewBackward
        case "=", "+": return .zoomIn
        case "-", "_": return .zoomOut
        case "q": return .turnLeft
        case "e": return .turnRight
        case "r": return .tiltUp
        case "f": return .tiltDown
        default: return nil
        }
    }

    private func readSpeed(_ flags: NSEvent.ModifierFlags) {
        speed = flags.contains(.shift) ? .fast : flags.contains(.control) ? .slow : .normal
    }

    /// Home (or 0): back to the first view.
    private static func isReset(_ event: NSEvent) -> Bool {
        event.keyCode == 115 || event.charactersIgnoringModifiers == "0"
    }

    override func keyDown(with event: NSEvent) {
        // ⌘ chords stay menu shortcuts (⌘W, ⌘3, ⌘Q…).
        if !event.modifierFlags.contains(.command), Self.isReset(event) {
            camera.goHome()
            apply()
            return
        }
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

    func makeNSView(context: Context) -> FreeLookSCNView {
        let view = FreeLookSCNView(frame: .zero)
        view.attach(model.scene.scene)
        return view
    }

    func updateNSView(_ view: FreeLookSCNView, context: Context) {
        view.setGround(model.groundSampler)
        if view.lastReset != model.resetCount {
            view.lastReset = model.resetCount
            let e = model.scene.extent
            view.reset(center: e.center, radius: e.radius)
        }
    }
}
