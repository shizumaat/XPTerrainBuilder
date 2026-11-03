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

/// `object_seat` (protocol 1.24, #1702): one object as the last build
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
    /// The zero the user set by hand (protocol 1.25, #1703); nil when none.
    public let userZeroM: Double?

    private enum CodingKeys: String, CodingKey {
        case seat, bodies, pending, zeroM = "zero_m", zeroMaxM = "zero_max_m", groundM = "ground_m"
        case heightM = "height_m", bottomM = "bottom_m", topM = "top_m", why, lines, plan
        case userZeroM = "user_zero_m"
    }

    /// Whether the object has a height its top and bottom differ by (the
    /// snap's Top / Bottom question, #1703).
    public var hasHeight: Bool {
        guard let topM, let bottomM else { return false }
        return topM - bottomM >= 0.05
    }
}

/// `object_seat_set` (protocol 1.25, #1703): the hand-set seat stored, and
/// the one it replaced (what Undo sends back). Zeros are metres MSL.
public struct O4ObjectSeatSet: Decodable, Equatable, Sendable {
    public let index: Int
    public let zeroM: Double?
    public let previousZeroM: Double?

    private enum CodingKeys: String, CodingKey {
        case index, zeroM = "zero_m", previousZeroM = "previous_zero_m"
    }
}
