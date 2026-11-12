import CoreGraphics
import XCTest
@testable import SceneryKit

/// The map's tile-state band (`TileBand`; Qt twin: tests/test_tile_band.py).
final class TileBandTests: XCTestCase {
    func testTheBandIsInsideTheTileAndScalesWithinItsLimits() {
        XCTAssertEqual(TileBand.band(px: 100), .init(mode: .band, inset: 1.5, width: 6))
        XCTAssertEqual(TileBand.band(px: TileBand.gradientMinPx).width, TileBand.widthMinPt)
        XCTAssertEqual(TileBand.band(px: 1000).width, TileBand.widthMaxPt)
        XCTAssertEqual(TileBand.band(px: 20).mode, .line)
        XCTAssertEqual(TileBand.band(px: 5), .init(mode: .line, inset: 0, width: 1))
    }

    func testNeighboursNeverOverlapAndTheGradientRunsInward() {
        let a = CGRect(x: 0, y: 0, width: 120, height: 120)
        let b = a.offsetBy(dx: 120, dy: 0)
        let band = TileBand.band(px: 120)
        let maxA = TileBand.sides(a, inset: band.inset, width: band.width)
            .flatMap { $0.polygon }.map(\.x).max()!
        let minB = TileBand.sides(b, inset: band.inset, width: band.width)
            .flatMap { $0.polygon }.map(\.x).min()!
        XCTAssertLessThan(maxA, minB)
        XCTAssertEqual(maxA, 120 - band.inset)
        for side in TileBand.sides(a, inset: band.inset, width: band.width) {
            let center = CGPoint(x: a.midX, y: a.midY)
            let dOuter = hypot(side.outer.x - center.x, side.outer.y - center.y)
            let dInner = hypot(side.inner.x - center.x, side.inner.y - center.y)
            XCTAssertEqual(dOuter - dInner, band.width, accuracy: 1e-9)
        }
    }
}
