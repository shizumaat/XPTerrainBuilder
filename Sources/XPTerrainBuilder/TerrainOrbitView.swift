import AppKit
import SceneKit
import SwiftUI
import simd

/// An `SCNView` with the preview's camera (spec §5): drag orbits, scroll
/// or pinch zooms, ⌥-drag (or right-drag) pans over the ground. Read-only:
/// no picking.
final class OrbitSCNView: SCNView {
    private let cameraNode = SCNNode()
    private var target = SIMD3<Float>(0, 0, 0)
    private var distance: Float = 2000
    private var azimuth: Float = 0
    private var elevation: Float = 0.6
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
        target = center
        distance = max(radius * 2.2, 50)
        azimuth = 0
        elevation = 0.6
        apply()
    }

    private func apply() {
        let c = cos(elevation)
        let offset = SIMD3<Float>(c * sin(azimuth), sin(elevation), c * cos(azimuth)) * distance
        cameraNode.position = TerrainPreviewScene.vector(target + offset)
        cameraNode.look(at: TerrainPreviewScene.vector(target))
    }

    override func mouseDragged(with event: NSEvent) {
        if event.modifierFlags.contains(.option) { pan(event); return }
        azimuth -= Float(event.deltaX) * 0.008
        elevation = min(max(elevation + Float(event.deltaY) * 0.008, 0.05), 1.55)
        apply()
    }

    override func rightMouseDragged(with event: NSEvent) { pan(event) }

    private func pan(_ event: NSEvent) {
        let k = distance * 0.0015
        let right = SIMD3<Float>(cos(azimuth), 0, -sin(azimuth))
        let forward = SIMD3<Float>(-sin(azimuth), 0, -cos(azimuth))
        target += (-right * Float(event.deltaX) + forward * Float(event.deltaY)) * k
        apply()
    }

    override func scrollWheel(with event: NSEvent) {
        let rate: Float = event.hasPreciseScrollingDeltas ? 0.005 : 0.05
        zoom(by: exp(-Float(event.scrollingDeltaY) * rate))
    }

    override func magnify(with event: NSEvent) { zoom(by: 1 / max(1 + Float(event.magnification), 0.1)) }

    private func zoom(by factor: Float) {
        distance = min(max(distance * factor, 20), 100_000)
        apply()
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
