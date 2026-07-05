import Foundation
import Combine

/// Stand-in for SwiftUI's @State, which can't be used when building with the
/// Command Line Tools toolchain (the SwiftUIMacros plugin only ships inside
/// Xcode). Use `@StateObject private var flag = ViewState(false)` and bind
/// with `$flag.value`.
final class ViewState<Value>: ObservableObject {
    @Published var value: Value

    init(_ initialValue: Value) {
        self.value = initialValue
    }
}
