import Foundation

/// One placed pack object on the patch editor's map (#1702): the
/// `pack_objects` placement it was drawn from, with its model's height
/// range — what the object inspector asks `object_seat` about, and what
/// the editor's next steps on a selected object (#1703 manual elevation)
/// key on: `index` is the DSF row the placement plan names it by.
public struct PackObjectRef: Equatable, Hashable, Sendable {
    public let index: Int
    public let model: String
    public let lat: Double
    public let lon: Double
    public let aglM: Double
    /// The model's authored height range (metres from its zero).
    public let yMin: Double?
    public let yMax: Double?

    public init(index: Int, model: String, lat: Double, lon: Double, aglM: Double,
                yMin: Double?, yMax: Double?) {
        self.index = index
        self.model = model
        self.lat = lat
        self.lon = lon
        self.aglM = aglM
        self.yMin = yMin
        self.yMax = yMax
    }
}

/// `object_seat` (protocol 1.25, #1702): one object as the last build
/// seated it. `lines` is the inspector's text (the engine writes it, so the
/// Mac app and the Qt window show the same words); the numbers are there
/// for the editor's next steps. Elevations are metres MSL.
public struct O4ObjectSeat: Decodable, Equatable, Sendable {
    /// `split`, `row`, `rider`, `converted`, `kept` or `authored` (the plan
    /// does not name it).
    public let seat: String
    public let bodies: Int
    public let pending: Bool
    /// Where the authored zero stands (lowest / highest over a split's bodies).
    public let zeroM: Double?
    public let zeroMaxM: Double?
    public let groundM: Double?
    public let heightM: Double?
    public let bottomM: Double?
    public let topM: Double?
    public let why: String
    public let lines: [String]
    /// The plan file's name; nil when the last build wrote none.
    public let plan: String?
    /// The zero the user set by hand (protocol 1.30, #1703); nil when none.
    public let userZeroM: Double?
    /// The object GROUP a placement the plan cut into parts moves with
    /// (capability `object_seat_groups`, #1970); nil for an uncut one.
    public let group: O4ObjectGroup?
    /// The lift the user gave that group over the build's seat (#1970).
    public let userOffsetM: Double?

    private enum CodingKeys: String, CodingKey {
        case seat, bodies, pending, zeroM = "zero_m", zeroMaxM = "zero_max_m", groundM = "ground_m"
        case heightM = "height_m", bottomM = "bottom_m", topM = "top_m", why, lines, plan
        case userZeroM = "user_zero_m", group, userOffsetM = "user_offset_m"
    }

    /// Whether the user set this object's (or its group's) elevation by hand.
    public var isHandSet: Bool { userZeroM != nil || userOffsetM != nil }

    /// Whether the object has a height its top and bottom differ by (the
    /// snap's Top / Bottom question, #1703).
    public var hasHeight: Bool {
        guard let topM, let bottomM else { return false }
        return topM - bottomM >= 0.05
    }
}

/// An object group (#1970, `o4_engine/object_group.py`): the placements
/// the plan cut into bodies of the same structure units, selected and
/// moved as one. `ring` is its outline, `[lat, lon]` corners.
public struct O4ObjectGroup: Decodable, Equatable, Sendable {
    public let rows: [Int]
    public let parts: Int
    public let sources: [String]
    public let ring: [[Double]]
}

/// `object_seat_set` (protocol 1.30, #1703): the hand-set seat stored, and
/// the one it replaced (what Undo sends back). Zeros are metres MSL; an
/// object group's seat is an offset (#1970).
public struct O4ObjectSeatSet: Decodable, Equatable, Sendable {
    public let index: Int
    public let zeroM: Double?
    public let previousZeroM: Double?
    public let offsetM: Double?
    public let previousOffsetM: Double?

    private enum CodingKeys: String, CodingKey {
        case index, zeroM = "zero_m", previousZeroM = "previous_zero_m"
        case offsetM = "offset_m", previousOffsetM = "previous_offset_m"
    }

    /// The seat now stored, and the one it replaced: an Undo sends `previous`.
    public var now: O4HandSeat { O4HandSeat(zeroM: zeroM, offsetM: offsetM) }
    public var previous: O4HandSeat { O4HandSeat(zeroM: previousZeroM, offsetM: previousOffsetM) }
}

/// A hand-set seat as `object_seat_set` takes it back: a zero, a group
/// offset (#1970), or neither (the build's own seat).
public struct O4HandSeat: Equatable, Sendable {
    public let zeroM: Double?
    public let offsetM: Double?

    public init(zeroM: Double?, offsetM: Double?) {
        self.zeroM = zeroM
        self.offsetM = offsetM
    }
}
