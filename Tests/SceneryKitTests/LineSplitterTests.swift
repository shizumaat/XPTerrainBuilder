import Foundation
import Testing
@testable import SceneryKit

/// Owner 1.0.398: the engine client re-scanned its whole stdout buffer on
/// every chunk, so one 50 MB `PackObjectsReady` line cost O(n²) and a patch
/// save's reply queued behind it. The witness is bytes searched, never wall
/// time.
@Suite struct LineSplitterTests {
    private static let chunk = 64 * 1024

    /// One `size`-byte line in 64 KB chunks, then 1,000 small lines; returns
    /// the splitter's bytes-scanned count after checking the split.
    private func feed(lineBytes size: Int) -> Int {
        var splitter = LineSplitter()
        var stream = Data(repeating: UInt8(ascii: "x"), count: size)
        stream.append(UInt8(ascii: "\n"))
        for i in 0..<1000 { stream.append(Data("line \(i)\n".utf8)) }
        var lines: [String] = []
        var offset = 0
        while offset < stream.count {
            let end = min(offset + Self.chunk, stream.count)
            lines += splitter.append(stream.subdata(in: offset..<end))
            offset = end
        }
        #expect(lines.count == 1001)
        #expect(lines[0].utf8.count == size)
        #expect(lines[0].utf8.allSatisfy { $0 == UInt8(ascii: "x") })
        #expect(lines[1] == "line 0")
        #expect(lines[1000] == "line 999")
        #expect(splitter.pendingCount == 0)
        #expect(splitter.bytesScanned == stream.count)
        return splitter.bytesScanned
    }

    @Test func longLineSplitsInLinearScan() {
        let small = feed(lineBytes: 10_000_000)
        let large = feed(lineBytes: 40_000_000)
        // Quadratic would be ~16x; linear is ~4x.
        let ratio = Double(large) / Double(small)
        #expect(ratio < 4.5, "bytes scanned 10 MB → 40 MB grew \(ratio)x")
    }

    @Test func fiftyMegabyteLineThenSmallLines() {
        _ = feed(lineBytes: 50_000_000)
    }

    @Test func partialLinesAndEmptyLinesAcrossChunks() {
        var splitter = LineSplitter()
        #expect(splitter.append(Data("ab".utf8)).isEmpty)
        #expect(splitter.append(Data("c\n\nd".utf8)) == ["abc", ""])
        #expect(splitter.pendingCount == 1)
        #expect(splitter.append(Data("e\nf\n".utf8)) == ["de", "f"])
        #expect(splitter.append(Data()).isEmpty)
        #expect(splitter.pendingCount == 0)
        #expect(splitter.bytesScanned == 10)
    }
}
