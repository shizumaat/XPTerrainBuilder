import AppKit
import SceneKit
import SceneryKit
import simd

/// The 3D preview's SceneKit graph (patch-editor spec §5): the terrain
/// with the patch cut out, one geometry per patch surface, and the
/// selected nodes as yellow markers. Vertical exaggeration is the scale of
/// `world`, so changing it rebuilds nothing; the markers live outside it so
/// they stay round. Holds no document state — `TerrainPreviewModel` feeds it.
@MainActor
final class TerrainPreviewScene {
    let scene = SCNScene()
    private let world = SCNNode()
    private let markerRoot = SCNNode()
    /// Outside `world`: buildings keep their true height; only their seat
    /// follows the exaggeration.
    private let buildingRoot = SCNNode()
    private var buildingNodes: [SCNNode] = []
    private var buildingPoses: [PatchBuildingPose] = []
    private var facadeNodes: [(node: SCNNode, baseY: Float)] = []
    private var terrainNode: SCNNode?
    private var terrainSources: [SCNGeometrySource] = []
    private var shapeNodes: [Int64: SCNNode] = [:]
    private var shapeElements: [Int64: SCNGeometryElement] = [:]
    private var markerPoints: [SIMD3<Float>] = []
    private(set) var exaggeration: Float = 3
    /// The ground extent (x/z centre and half-size, metres) the camera
    /// frames on "Reset view".
    private(set) var extent: (center: SIMD3<Float>, radius: Float) = (.zero, 1000)

    static let terrainColor = NSColor(srgbRed: 0x7a / 255, green: 0x8a / 255, blue: 0x6a / 255, alpha: 1)
    static let patchColor = NSColor(srgbRed: 0xd6 / 255, green: 0xda / 255, blue: 0xe2 / 255, alpha: 1)
    static let buildingColor = NSColor(srgbRed: 0xb9 / 255, green: 0xbe / 255, blue: 0xc8 / 255, alpha: 1)
    static let markerColor = NSColor(srgbRed: 1.0, green: 0.84, blue: 0.04, alpha: 1)   // #FFD60A
    static let background = NSColor(srgbRed: 0x0b / 255, green: 0x0d / 255, blue: 0x12 / 255, alpha: 1)

    private let terrainMaterial = TerrainPreviewScene.material(terrainColor)
    private let patchMaterial = TerrainPreviewScene.material(patchColor)
    private let buildingMaterial = TerrainPreviewScene.material(buildingColor)
    private let markerGeometry: SCNGeometry = {
        let sphere = SCNSphere(radius: 1.8)
        let m = SCNMaterial()
        m.lightingModel = .constant
        m.diffuse.contents = TerrainPreviewScene.markerColor
        sphere.materials = [m]
        return sphere
    }()

    init() {
        scene.background.contents = Self.background
        scene.rootNode.addChildNode(world)
        scene.rootNode.addChildNode(markerRoot)
        scene.rootNode.addChildNode(buildingRoot)
        world.scale = SCNVector3(1, CGFloat(exaggeration), 1)

        let sun = SCNNode()
        sun.light = SCNLight()
        sun.light?.type = .directional
        sun.light?.intensity = 900
        sun.eulerAngles = SCNVector3(-CGFloat.pi / 3, CGFloat.pi / 5, 0)
        scene.rootNode.addChildNode(sun)
        let ambient = SCNNode()
        ambient.light = SCNLight()
        ambient.light?.type = .ambient
        ambient.light?.intensity = 350
        scene.rootNode.addChildNode(ambient)
    }

    private static func material(_ color: NSColor) -> SCNMaterial {
        let m = SCNMaterial()
        m.diffuse.contents = color
        m.lightingModel = .lambert
        m.isDoubleSided = true
        return m
    }

    // MARK: - Terrain

    func setTerrain(_ mesh: PatchTerrainMesh, indices: [UInt32], extent: (SIMD3<Float>, Float)) {
        terrainNode?.removeFromParentNode()
        terrainSources = [Self.source(mesh.positions, .vertex), Self.source(mesh.normals, .normal)]
        let node = SCNNode()
        world.addChildNode(node)
        terrainNode = node
        self.extent = (extent.0, extent.1)
        setTerrainIndices(indices)
    }

    /// The cut-out changed (a node moved): swap the index buffer only.
    func setTerrainIndices(_ indices: [UInt32]) {
        guard let terrainNode, !terrainSources.isEmpty else { return }
        let geometry = SCNGeometry(sources: terrainSources, elements: [Self.element(indices)])
        geometry.materials = [terrainMaterial]
        terrainNode.geometry = geometry
    }

    // MARK: - Patch shapes

    /// One shape's buffer. `indices` nil keeps the shape's triangles (a
    /// node moved or changed elevation); a new list re-triangulated it.
    func setShape(_ way: Int64, positions: [SIMD3<Float>], normals: [SIMD3<Float>], indices: [UInt32]?) {
        if let indices { shapeElements[way] = Self.element(indices) }
        guard let element = shapeElements[way] else { return }
        let geometry = SCNGeometry(sources: [Self.source(positions, .vertex), Self.source(normals, .normal)],
                                   elements: [element])
        geometry.materials = [patchMaterial]
        if let node = shapeNodes[way] {
            node.geometry = geometry
        } else {
            let node = SCNNode(geometry: geometry)
            world.addChildNode(node)
            shapeNodes[way] = node
        }
    }

    func removeShape(_ way: Int64) {
        shapeNodes.removeValue(forKey: way)?.removeFromParentNode()
        shapeElements.removeValue(forKey: way)
    }

    func removeAll() {
        terrainNode?.removeFromParentNode(); terrainNode = nil; terrainSources = []
        for way in Array(shapeNodes.keys) { removeShape(way) }
        setMarkers([])
        removeBuildings()
    }

    // MARK: - Selection, exaggeration, wireframe

    /// Points in unexaggerated preview space.
    func setMarkers(_ points: [SIMD3<Float>]) {
        markerPoints = points
        markerRoot.childNodes.forEach { $0.removeFromParentNode() }
        for p in points {
            let node = SCNNode(geometry: markerGeometry)
            node.position = Self.vector(SIMD3(p.x, p.y * exaggeration, p.z))
            markerRoot.addChildNode(node)
        }
    }

    func setExaggeration(_ value: Float) {
        exaggeration = value
        world.scale = SCNVector3(1, CGFloat(value), 1)
        for (node, p) in zip(markerRoot.childNodes, markerPoints) {
            node.position = Self.vector(SIMD3(p.x, p.y * value, p.z))
        }
        for i in buildingNodes.indices { seat(i) }
        for f in facadeNodes { f.node.position.y = CGFloat(f.baseY * value) }
    }

    func setWireframe(_ on: Bool) {
        for m in [terrainMaterial, patchMaterial, buildingMaterial] { m.fillMode = on ? .lines : .fill }
    }

    // MARK: - Buildings (spec §5: grey massing, shared geometry + clones)

    /// One shared geometry per model; one node per placement.
    func setBuildings(models: [String: SCNGeometry], placements: [String],
                      poses: [PatchBuildingPose], facades: [(SCNGeometry, Float)]) {
        removeBuildings()
        for geometry in models.values { geometry.materials = [buildingMaterial] }
        for (key, pose) in zip(placements, poses) {
            guard let geometry = models[key] else { continue }
            let node = SCNNode(geometry: geometry)
            buildingRoot.addChildNode(node)
            buildingNodes.append(node)
            buildingPoses.append(pose)
            seat(buildingNodes.count - 1)
        }
        for (geometry, baseY) in facades {
            geometry.materials = [buildingMaterial]
            let node = SCNNode(geometry: geometry)
            node.position = SCNVector3(0, CGFloat(baseY * exaggeration), 0)
            buildingRoot.addChildNode(node)
            facadeNodes.append((node, baseY))
        }
    }

    /// New poses for some placements (an edit moved their ground).
    func reseatBuildings(_ indices: [Int], poses: [PatchBuildingPose]) {
        for i in indices where i < buildingNodes.count {
            buildingPoses[i] = poses[i]
            seat(i)
        }
    }

    func setBuildingsVisible(_ on: Bool) { buildingRoot.isHidden = !on }

    private func seat(_ i: Int) {
        let pose = buildingPoses[i]
        buildingNodes[i].position = Self.vector(SIMD3(pose.position.x, pose.position.y * exaggeration,
                                                      pose.position.z))
        buildingNodes[i].eulerAngles = SCNVector3(0, CGFloat(pose.yaw), 0)
    }

    private func removeBuildings() {
        buildingRoot.childNodes.forEach { $0.removeFromParentNode() }
        buildingNodes = []; buildingPoses = []; facadeNodes = []
    }

    /// A model's grey massing as one geometry (flat-shaded hulls).
    nonisolated static func modelGeometry(vertices: [Float], triangles: [UInt32]) -> SCNGeometry {
        var p: [SIMD3<Float>] = []
        p.reserveCapacity(triangles.count)
        for i in triangles { let k = Int(i) * 3; p.append(SIMD3(vertices[k], vertices[k + 1], vertices[k + 2])) }
        let flat = Array(0..<UInt32(p.count))
        return SCNGeometry(sources: [source(p, .vertex), source(PatchPreviewNormals.of(positions: p, indices: flat), .normal)],
                           elements: [element(flat)])
    }

    /// A facade as a prism: walls from 0 to `height` over the ring (in
    /// preview metres, relative to its base), and a flat roof.
    nonisolated static func facadeGeometry(ring: [SIMD2<Float>], height: Float) -> SCNGeometry {
        var p: [SIMD3<Float>] = []
        for i in ring.indices {
            let a = ring[i], b = ring[(i + 1) % ring.count]
            let q = [SIMD3(a.x, 0, a.y), SIMD3(b.x, 0, b.y), SIMD3(b.x, height, b.y), SIMD3(a.x, height, a.y)]
            p += [q[0], q[1], q[2], q[0], q[2], q[3]]
        }
        let roof = PatchTriangulator.triangulate(coordinates: ring.flatMap { [Double($0.x), Double(-$0.y)] })
        for i in roof { p.append(SIMD3(ring[i].x, height, ring[i].y)) }
        let idx = Array(0..<UInt32(p.count))
        return SCNGeometry(sources: [source(p, .vertex), source(PatchPreviewNormals.of(positions: p, indices: idx), .normal)],
                           elements: [element(idx)])
    }

    // MARK: - Buffers

    private nonisolated static func source(_ v: [SIMD3<Float>], _ semantic: SCNGeometrySource.Semantic) -> SCNGeometrySource {
        let stride = MemoryLayout<SIMD3<Float>>.stride
        let data = v.withUnsafeBytes { Data($0) }
        return SCNGeometrySource(data: data, semantic: semantic, vectorCount: v.count,
                                 usesFloatComponents: true, componentsPerVector: 3,
                                 bytesPerComponent: MemoryLayout<Float>.size, dataOffset: 0, dataStride: stride)
    }

    private nonisolated static func element(_ indices: [UInt32]) -> SCNGeometryElement {
        SCNGeometryElement(data: indices.withUnsafeBytes { Data($0) }, primitiveType: .triangles,
                           primitiveCount: indices.count / 3, bytesPerIndex: MemoryLayout<UInt32>.size)
    }

    static func vector(_ p: SIMD3<Float>) -> SCNVector3 {
        SCNVector3(CGFloat(p.x), CGFloat(p.y), CGFloat(p.z))
    }
}
