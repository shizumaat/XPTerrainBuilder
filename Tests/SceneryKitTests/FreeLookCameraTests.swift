import Testing
import simd
@testable import SceneryKit

/// The free-look camera (#794): the scene is fixed, the eye moves and
/// looks around. Twin of `tests/test_qt_preview3d.py`'s FreeLook tests.
struct FreeLookCameraTests {
    private func camera(ground: ((Float, Float) -> Float?)? = nil) -> FreeLookCamera {
        var c = FreeLookCamera(ground: ground)
        c.reset(center: .zero, radius: 1000)
        return c
    }

    @Test func theFirstViewIsAboveAndOutsideTheBoxAimedAtItsCentre() {
        let c = camera()
        #expect(c.shown.eye.y > 1000 && c.shown.eye.z > 1000)     // above, south of the box
        let toCentre = simd_normalize(-c.shown.eye)
        #expect(simd_dot(c.lookDirection, toCentre) > 0.9999)
    }

    @Test func aDragTurnsTheViewAndNeverMovesTheEye() {
        var c = camera()
        let eye = c.goal.eye, pitch = c.goal.pitch
        c.look(dx: 100, dy: 0)
        #expect(c.goal.eye == eye && c.goal.pitch == pitch)
        #expect(c.goal.heading > 0)                                // dragging right turns right
        while c.step(dt: 1.0 / 60) {}
        #expect(c.shown.eye == eye && c.lookDirection.x > 0)       // now looking a little east
        c.look(dx: 0, dy: -50)                                     // drag up looks up
        #expect(c.goal.pitch > pitch && c.goal.eye == eye)
    }

    @Test func forwardMovesTheEyeAlongTheHeading() {
        var c = camera()
        c.look(dx: 300, dy: 0)                                     // turned right of north
        let eye = c.goal.eye, h = c.goal.heading
        c.hold([.forward], speed: .normal, dt: 1)
        let d = c.goal.eye - eye
        #expect(abs(d.y) < 1e-3)                                   // ↑ stays level
        #expect(abs(atan2(d.x, -d.z) - h) < 1e-4)                  // along the heading
        c = camera(); let e0 = c.goal.eye
        c.hold([.viewForward], speed: .normal, dt: 1)              // `.` follows the view, down
        #expect(c.goal.eye.y < e0.y && c.goal.eye.z < e0.z)
        c = camera(); c.hold([.right], speed: .normal, dt: 1)
        #expect(c.goal.eye.x > 0)
        c = camera(); c.scroll(10, precise: false)                 // scroll moves along the view
        #expect(c.goal.eye.y < e0.y && c.goal.eye.z < e0.z && c.goal.fov == c.home.fov)
    }

    @Test func zoomKeysChangeTheFieldOfViewOnly() {
        var c = camera(); let eye = c.goal.eye
        c.hold([.zoomIn], speed: .normal, dt: 1)
        #expect(c.goal.fov < FreeLookCamera.defaultFov && c.goal.eye == eye)
        c.hold([.zoomOut], speed: .fast, dt: 10)
        #expect(c.goal.fov == FreeLookCamera.maxFov)
    }

    @Test func shiftIsFasterAndControlSlowerThanPlainKeys() {
        var slow = camera(), plain = camera(), fast = camera()
        slow.hold([.turnLeft], speed: .slow, dt: 0.5)
        plain.hold([.turnLeft], speed: .normal, dt: 0.5)
        fast.hold([.turnLeft], speed: .fast, dt: 0.5)
        #expect(slow.goal.heading < 0)                             // Q turns left
        #expect(plain.goal.heading == slow.goal.heading * 4)
        #expect(fast.goal.heading == plain.goal.heading * 4)
        var c = camera(); c.hold([.turnLeft, .turnRight], speed: .fast, dt: 1)
        #expect(c.goal.heading == 0)                               // opposite keys cancel
    }

    @Test func pitchClampsAtEightyNineDegrees() {
        var c = camera()
        c.hold([.tiltUp], speed: .fast, dt: 10)
        #expect(c.goal.pitch == FreeLookCamera.maxPitch)
        c.look(dx: 0, dy: 100_000)
        #expect(c.goal.pitch == -FreeLookCamera.maxPitch)
    }

    @Test func theEyeStaysAboveTheTerrain() {
        // a hill rising to the north: y = 0.5 × distance north of z = 0
        var c = camera { _, z in max(-z, 0) * 0.5 }
        for _ in 0..<600 {
            c.hold([.viewForward], speed: .fast, dt: 1.0 / 60)
            c.step(dt: 1.0 / 60)
            let g = max(-c.shown.eye.z, 0) * 0.5
            #expect(c.shown.eye.y >= g + FreeLookCamera.minClearance - 1e-3)
            #expect(c.goal.eye.y >= g + FreeLookCamera.minClearance - 1e-3 || c.goal.eye.z > -1)
        }
        #expect(c.shown.eye.z < 0)                                 // it went over the hill, not into it
    }

    @Test func resetRestoresTheFirstView() {
        var c = camera()
        let first = c.shown
        c.look(dx: 400, dy: 80)
        c.hold([.forward, .zoomIn, .tiltUp], speed: .fast, dt: 1)
        c.step(dt: 0.5)
        c.goHome()
        #expect(c.shown == first && c.goal == first)
    }

    @Test func theShownCameraEasesToTheGoalInsteadOfJumping() {
        var c = camera()
        c.look(dx: 200, dy: 0)
        let goal = c.goal.heading
        c.step(dt: 1.0 / 60)
        #expect(c.shown.heading > 0 && c.shown.heading < goal * 0.5)
        var frames = 0
        while c.step(dt: 1.0 / 60) { frames += 1 }
        #expect(c.shown == c.goal && frames < 120)
    }

    @Test func aMouseDragTurnsLessThanTheFirstCut() {
        var c = camera()
        c.look(dx: 100, dy: 0)
        #expect(abs(c.goal.heading) < 100 * 0.008 / 2)
    }
}
