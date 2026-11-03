import Testing
import Foundation
@testable import SceneryKit

/// Shape nodes snap to an object's footprint corners and edge middles (#1703).
struct PatchObjectSnapTests {
    @Test func cornersThenEdgeMiddles() {
        let square: [SIMD2<Double>] = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        let v = PatchObjectSnap.vertices(square)
        #expect(v.count == 8)
        #expect(Array(v.prefix(4)) == Array(square.prefix(4)))
        #expect(v[4] == [5, 0] && v[7] == [0, 5])
    }

    @Test func nearestWithinTheRadius() {
        let points: [SIMD2<Double>] = [[0, 0], [5, 0], [10, 0]]
        #expect(PatchObjectSnap.nearest([4, 1], in: points, radius: 8) == 1)
        #expect(PatchObjectSnap.nearest([30, 30], in: points, radius: 8) == nil)
    }

    @Test func seatDecodesTheHandSetZero() throws {
        let json = """
        {"seat": "row", "bodies": 0, "pending": false, "zero_m": 55, "zero_max_m": 55, "ground_m": null,
         "height_m": 4, "bottom_m": 54, "top_m": 58, "why": "Set by hand at 55.0 m MSL",
         "lines": [], "plan": null, "user_zero_m": 55}
        """
        let seat = try JSONDecoder().decode(O4ObjectSeat.self, from: Data(json.utf8))
        #expect(seat.userZeroM == 55 && seat.hasHeight)
        #expect(O4ProtocolVersion.supportsObjectSeatSet("1.25") && !O4ProtocolVersion.supportsObjectSeatSet("1.24"))
    }
}
