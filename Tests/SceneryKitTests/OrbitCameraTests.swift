import Testing
import simd
@testable import SceneryKit

struct OrbitCameraTests {
    private func camera() -> OrbitCamera {
        var c = OrbitCamera()
        c.reset(center: .zero, radius: 1000)
        return c
    }

    @Test func shiftIsFasterAndControlSlowerThanPlainKeys() {
        var slow = camera(), plain = camera(), fast = camera()
        slow.hold([.rotateLeft], speed: .slow, dt: 0.5)
        plain.hold([.rotateLeft], speed: .normal, dt: 0.5)
        fast.hold([.rotateLeft], speed: .fast, dt: 0.5)
        #expect(slow.goal.azimuth > 0)
        #expect(plain.goal.azimuth == slow.goal.azimuth * 4)
        #expect(fast.goal.azimuth == plain.goal.azimuth * 4)
    }

    @Test func xPlaneKeysMoveTheRightAxes() {
        var c = camera()
        c.hold([.tiltUp], speed: .normal, dt: 1)
        #expect(c.goal.elevation > 0.6)
        c = camera(); c.hold([.forward], speed: .normal, dt: 1)
        #expect(c.goal.target.z < 0)                 // north, the way the camera looks
        c = camera(); c.hold([.right], speed: .normal, dt: 1)
        #expect(c.goal.target.x > 0)
        c = camera(); c.hold([.up], speed: .normal, dt: 1)
        #expect(c.goal.target.y > 0)
        c = camera(); let d = c.goal.distance; c.hold([.zoomIn], speed: .normal, dt: 1)
        #expect(c.goal.distance < d)
        c = camera(); c.hold([.rotateLeft, .rotateRight], speed: .fast, dt: 1)
        #expect(c.goal.azimuth == 0)                 // opposite keys cancel
    }

    @Test func tiltStaysBetweenTheHorizonAndStraightDown() {
        var c = camera()
        c.hold([.tiltUp], speed: .fast, dt: 10)
        #expect(c.goal.elevation == OrbitCamera.maxElevation)
        c.hold([.tiltDown], speed: .fast, dt: 10)
        #expect(c.goal.elevation == OrbitCamera.minElevation)
    }

    @Test func theShownCameraEasesToTheGoalInsteadOfJumping() {
        var c = camera()
        c.orbit(dx: 200, dy: 0)
        let goal = c.goal.azimuth
        c.step(dt: 1.0 / 60)
        #expect(abs(c.shown.azimuth) > 0 && abs(c.shown.azimuth) < abs(goal) * 0.5)
        var frames = 0
        while c.step(dt: 1.0 / 60) { frames += 1 }
        #expect(c.shown == c.goal && frames < 120)
    }

    @Test func aMouseDragTurnsLessThanTheFirstCut() {
        var c = camera()
        c.orbit(dx: 100, dy: 0)
        #expect(abs(c.goal.azimuth) < 100 * 0.008 / 2)
    }
}
