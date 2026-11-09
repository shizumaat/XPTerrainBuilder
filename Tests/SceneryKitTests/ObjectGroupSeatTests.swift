import Testing
import Foundation
@testable import SceneryKit

/// An object the build cut into parts answers for its whole group, and
/// its hand-set seat is a group offset (#1970, `o4_engine/object_group.py`).
struct ObjectGroupSeatTests {
    @Test func seatDecodesTheGroup() throws {
        let json = """
        {"seat": "group", "bodies": 5, "pending": false, "zero_m": 52, "zero_max_m": 102.5,
         "ground_m": null, "height_m": null, "bottom_m": 52, "top_m": null,
         "why": "Moved by hand +2.00 m from the build's seat", "lines": ["Group of 3 objects, 5 parts"],
         "plan": "o4_v2_placement_ZZZZ.json", "user_zero_m": null, "user_offset_m": 2.0, "index": 2,
         "group": {"rows": [1, 2, 4], "parts": 5, "sources": ["roof.obj"],
                   "ring": [[45.1, -122.9], [45.1, -122.8998], [45.1009, -122.8998]]}}
        """
        let seat = try JSONDecoder().decode(O4ObjectSeat.self, from: Data(json.utf8))
        #expect(seat.group?.rows == [1, 2, 4] && seat.group?.ring.count == 3)
        #expect(seat.userOffsetM == 2.0 && seat.isHandSet && !seat.hasHeight)
    }

    @Test func undoSendsTheReplacedOffset() throws {
        let json = """
        {"index": 2, "zero_m": null, "previous_zero_m": null, "offset_m": 2.0, "previous_offset_m": 0.5,
         "rows": [1, 2, 4]}
        """
        let reply = try JSONDecoder().decode(O4ObjectSeatSet.self, from: Data(json.utf8))
        #expect(reply.now == O4HandSeat(zeroM: nil, offsetM: 2.0))
        #expect(reply.previous == O4HandSeat(zeroM: nil, offsetM: 0.5))
        let old = try JSONDecoder().decode(O4ObjectSeatSet.self,
                                           from: Data(#"{"index": 1, "zero_m": 3, "previous_zero_m": null}"#.utf8))
        #expect(old.previous == O4HandSeat(zeroM: nil, offsetM: nil))
    }
}
