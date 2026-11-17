import Testing
import Foundation
@testable import SceneryKit

/// The engine's environment carries no `MallocStackLogging*` variable —
/// the Swift half of `Ortho4XP/tests/test_process_environment.py`.
@Suite struct ProcessEnvironmentTests {

    @Test func mallocStackLoggingVariablesAreRemovedNotZeroed() {
        let env = OrthoProcessRunner.environment(from: [
            "PATH": "/usr/bin",
            "MallocStackLogging": "0",
            "MallocStackLoggingNoCompact": "1",
            "MallocStackLoggingDirectory": "/tmp",
            "__XPC_MallocStackLogging": "1",
            "MallocNanoZone": "0",
            "HOME": "/Users/x",
        ])
        #expect(env.keys.allSatisfy { !$0.contains("MallocStackLogging") })
        #expect(env["MallocNanoZone"] == "0")
        #expect(env["HOME"] == "/Users/x")
        #expect(env["PYTHONUNBUFFERED"] == "1")
        #expect(env["PATH"]?.hasPrefix("/usr/bin") == true)
    }
}
