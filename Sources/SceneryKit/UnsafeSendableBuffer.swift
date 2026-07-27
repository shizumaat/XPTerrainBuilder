import Foundation

/// Wrapper to move an UnsafeMutableBufferPointer across concurrentPerform's
/// Sendable boundary. Safe here because each iteration writes a distinct index.
struct UnsafeSendableBuffer<T>: @unchecked Sendable {
    let buffer: UnsafeMutableBufferPointer<T>
    init(_ buffer: UnsafeMutableBufferPointer<T>) { self.buffer = buffer }
}
