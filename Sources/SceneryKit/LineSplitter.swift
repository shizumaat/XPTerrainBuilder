import Foundation

/// Splits a byte stream that arrives in chunks into newline-terminated
/// lines, in time linear in the bytes received.
///
/// Every byte is searched for a newline exactly once: `scanFrom` remembers
/// how far the pending (unterminated) tail has already been searched, so a
/// very long line delivered in many chunks — the engine's `PackObjectsReady`
/// reply is tens of MB on one line — is not re-scanned from its start on
/// each chunk. Consumed lines are dropped from the front once per chunk, not
/// once per line; the bytes kept are only the tail after the last newline of
/// this chunk, so that copy is bounded by the chunk.
///
/// Not thread-safe; the owner serialises access (OrthoEngineClient holds its
/// lock around `append`).
public struct LineSplitter: Sendable {
    private var buffer = Data()
    private var scanFrom = 0
    /// Bytes searched for a newline so far: the test's linear-time witness.
    public private(set) var bytesScanned = 0

    public init() {}

    /// Bytes received but not yet terminated by a newline.
    public var pendingCount: Int { buffer.count }

    /// Append a chunk; returns the lines it completed, without their `\n`.
    public mutating func append(_ data: Data) -> [String] {
        buffer.append(data)
        var lines: [String] = []
        var lineStart = buffer.startIndex
        var cursor = buffer.startIndex + scanFrom
        let newline = UInt8(ascii: "\n")
        while cursor < buffer.endIndex,
              let nl = buffer[cursor...].firstIndex(of: newline) {
            bytesScanned += nl - cursor + 1
            lines.append(String(decoding: buffer[lineStart..<nl], as: UTF8.self))
            lineStart = nl + 1
            cursor = lineStart
        }
        bytesScanned += buffer.endIndex - cursor
        if lineStart > buffer.startIndex {
            buffer = Data(buffer[lineStart...])
        }
        scanFrom = buffer.count
        return lines
    }
}
