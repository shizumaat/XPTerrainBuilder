import Foundation
import Darwin

/// One tile build request, serialized as the driver's job JSON.
public struct OrthoBuildJob: Codable, Sendable, Equatable {
    public var lat: Int
    public var lon: Int
    /// Subset of "vector", "mesh", "masks", "dsf", "overlay", in run order.
    public var steps: [String]
    public var provider: String?
    public var zl: Int?
    /// Custom tile base folder; "" uses the engine's Tiles/.
    public var buildDir: String
    public var tileOverrides: [String: O4Value]
    public var appOverrides: [String: O4Value]

    public init(lat: Int, lon: Int, steps: [String],
                provider: String? = nil, zl: Int? = nil, buildDir: String = "",
                tileOverrides: [String: O4Value] = [:],
                appOverrides: [String: O4Value] = [:]) {
        self.lat = lat
        self.lon = lon
        self.steps = steps
        self.provider = provider
        self.zl = zl
        self.buildDir = buildDir
        self.tileOverrides = tileOverrides
        self.appOverrides = appOverrides
    }

    enum CodingKeys: String, CodingKey {
        case lat, lon, steps, provider, zl
        case buildDir = "build_dir"
        case tileOverrides = "tile_overrides"
        case appOverrides = "app_overrides"
    }

    public static let allSteps = ["vector", "mesh", "masks", "dsf"]

    public static func stepLabel(_ step: String) -> String {
        switch step {
        case "vector": return "Assemble vector data"
        case "mesh": return "Triangulate 3D mesh"
        case "masks": return "Draw water masks"
        case "dsf": return "Build imagery / DSF"
        case "overlay": return "Extract overlays"
        default: return step
        }
    }
}

public enum OrthoBuildOutcome: String, Sendable {
    case ok, fail, stopped
}

/// Parsed driver output. The engine's three progress bars keep their ids:
/// 1 = mesh, 2 = imagery download, 3 = DDS conversion.
public enum OrthoBuildEvent: Sendable, Equatable {
    case console(String)
    case engineVersion(String)
    case progress(bar: Int, percent: Int)
    case stepStarted(String)
    case stepFinished(String, ok: Bool)
    case stepSkipped(String)
    case stopping
    case fatal(String)
    case exit(OrthoBuildOutcome)

    /// One line of driver stdout → event. Anything not carrying the @@O4|
    /// marker is engine console output.
    public static func parse(line: String) -> OrthoBuildEvent {
        guard line.hasPrefix("@@O4|") else { return .console(line) }
        let fields = line.dropFirst("@@O4|".count).components(separatedBy: "|")
        switch fields.first {
        case "engine" where fields.count >= 2:
            return .engineVersion(fields[1])
        case "progress" where fields.count >= 3:
            if let bar = Int(fields[1]), let pct = Int(fields[2]) {
                return .progress(bar: bar, percent: min(max(pct, 0), 100))
            }
        case "step" where fields.count >= 3:
            switch fields[2] {
            case "start": return .stepStarted(fields[1])
            case "ok": return .stepFinished(fields[1], ok: true)
            case "fail": return .stepFinished(fields[1], ok: false)
            case "skip": return .stepSkipped(fields[1])
            default: break
            }
        case "stopping":
            return .stopping
        case "fatal":
            return .fatal(fields.dropFirst().joined(separator: "|"))
        case "exit" where fields.count >= 2:
            if let outcome = OrthoBuildOutcome(rawValue: fields[1]) {
                return .exit(outcome)
            }
        default:
            break
        }
        return .console(line)
    }
}

/// Spawns a process and delivers its merged stdout/stderr line by line.
/// Shared by the build runner and the environment-setup runner.
public final class OrthoProcessRunner: @unchecked Sendable {
    private let process = Process()
    private let stdinPipe = Pipe()
    private let outputPipe = Pipe()
    private let lock = NSLock()
    private var buffer = Data()
    private var onLine: (@Sendable (String) -> Void)?

    public init() {}

    public var isRunning: Bool { process.isRunning }
    public private(set) var launched = false

    /// Writable data root handed to every engine process as
    /// ORTHO4XP_DATA_ROOT: downloads, caches, built tiles and the global
    /// config land there instead of inside the (possibly read-only) engine
    /// folder. The app sets this from the user's data-folder choice; nil
    /// keeps the engine's own default (its install folder).
    nonisolated(unsafe) public static var dataRoot: String?

    /// PATH extended with the Homebrew locations the engine's optional
    /// tools (gdal, 7z) usually live in — the app's own environment won't
    /// have a login shell's PATH.
    static func environment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        let extras = ["/opt/homebrew/bin", "/usr/local/bin"]
        var path = env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin"
        for extra in extras where !path.components(separatedBy: ":").contains(extra) {
            path += ":" + extra
        }
        env["PATH"] = path
        // Line-buffered engine output even through a pipe.
        env["PYTHONUNBUFFERED"] = "1"
        if let dataRoot, !dataRoot.isEmpty {
            env["ORTHO4XP_DATA_ROOT"] = dataRoot
        }
        return env
    }

    public func launch(executable: URL, arguments: [String], workingDirectory: URL,
                       onLine: @escaping @Sendable (String) -> Void,
                       onExit: @escaping @Sendable (Int32) -> Void) throws {
        self.onLine = onLine
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = workingDirectory
        process.environment = Self.environment()
        process.standardInput = stdinPipe
        process.standardOutput = outputPipe
        process.standardError = outputPipe

        outputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self else { return }
            if data.isEmpty {
                handle.readabilityHandler = nil
                self.flushRemainder()
                return
            }
            self.consume(data)
        }
        process.terminationHandler = { [weak self] proc in
            // The readability handler may still hold the last partial line.
            self?.flushRemainder()
            onExit(proc.terminationStatus)
        }
        try process.run()
        launched = true
    }

    private func consume(_ data: Data) {
        var lines: [String] = []
        lock.lock()
        buffer.append(data)
        while let nl = buffer.firstIndex(of: UInt8(ascii: "\n")) {
            let lineData = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            lines.append(String(decoding: lineData, as: UTF8.self))
        }
        lock.unlock()
        for line in lines { onLine?(line) }
    }

    private func flushRemainder() {
        lock.lock()
        let rest = buffer
        buffer = Data()
        lock.unlock()
        if !rest.isEmpty {
            onLine?(String(decoding: rest, as: UTF8.self))
        }
    }

    /// Write a line to the child's stdin (the driver's STOP channel).
    public func send(line: String) {
        guard process.isRunning else { return }
        stdinPipe.fileHandleForWriting.write(Data((line + "\n").utf8))
    }

    public func terminate() {
        guard process.isRunning else { return }
        process.terminate()
    }

    public func kill() {
        guard process.isRunning else { return }
        Darwin.kill(process.processIdentifier, SIGKILL)
    }
}

/// Runs one driver job against an engine. One runner per tile build; the
/// queueing of multiple tiles lives in the app's build model.
public final class OrthoBuildRunner: @unchecked Sendable {
    private let runner = OrthoProcessRunner()
    private var jobFileURL: URL?

    public init() {}

    public var isRunning: Bool { runner.isRunning }

    /// The driver script shipped in this package's resources.
    public static func driverScriptURL() -> URL? {
        Bundle.module.url(forResource: "o4_driver", withExtension: "py")
    }

    public static func schemaDumpScriptURL() -> URL? {
        Bundle.module.url(forResource: "o4_schema_dump", withExtension: "py")
    }

    /// Launches the job. Events stream on an arbitrary background thread;
    /// `onExit` fires exactly once after the process ends (whether or not
    /// the driver managed to emit an exit event).
    public func start(job: OrthoBuildJob, engine: OrthoEngine,
                      onEvent: @escaping @Sendable (OrthoBuildEvent) -> Void,
                      onExit: @escaping @Sendable (Int32) -> Void) throws {
        // Frozen engines always speak the session protocol; the loose-script
        // driver can't run inside them.
        guard !engine.isFrozen else {
            throw CocoaError(.featureUnsupported, userInfo: [
                NSLocalizedDescriptionKey: "The bundled engine uses the session protocol, not the legacy driver."])
        }
        guard let driver = Self.driverScriptURL() else {
            throw CocoaError(.fileNoSuchFile, userInfo: [
                NSLocalizedDescriptionKey: "The bundled Ortho4XP driver script is missing."])
        }
        let jobURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("o4-job-\(UUID().uuidString).json")
        let encoder = JSONEncoder()
        try encoder.encode(job).write(to: jobURL)
        jobFileURL = jobURL

        try runner.launch(
            executable: engine.pythonURL,
            arguments: ["-u", driver.path, jobURL.path],
            workingDirectory: engine.root,
            onLine: { line in onEvent(OrthoBuildEvent.parse(line: line)) },
            onExit: { [weak self] status in
                if let url = self?.jobFileURL {
                    try? FileManager.default.removeItem(at: url)
                }
                onExit(status)
            })
    }

    /// Graceful stop: raises the engine's red flag via the driver's stdin.
    /// The current step finishes its abort path and the process exits.
    public func requestStop() {
        runner.send(line: "STOP")
    }

    /// Hard stop for when graceful didn't take (native subprocesses don't
    /// poll the red flag).
    public func kill() {
        runner.kill()
    }

    // MARK: - Schema extraction

    /// Runs the schema dump against the engine, returning the decoded
    /// schema. Synchronous — call from a background task. Falls back to nil
    /// on any failure (caller uses the bundled snapshot).
    public static func extractSchema(engine: OrthoEngine) -> OrthoConfigSchema? {
        // Frozen engines can't run loose scripts; the bundled snapshot —
        // generated from the same engine sources — stands in.
        guard !engine.isFrozen else { return nil }
        guard let script = schemaDumpScriptURL() else { return nil }
        let process = Process()
        process.executableURL = engine.pythonURL
        process.arguments = [script.path]
        process.currentDirectoryURL = engine.root
        process.environment = OrthoProcessRunner.environment()
        let out = Pipe()
        process.standardOutput = out
        process.standardError = Pipe()
        do {
            try process.run()
        } catch {
            return nil
        }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { return nil }
        return try? OrthoConfigSchema.decode(from: data)
    }

    /// Quick readiness probe: can the engine's python import the third-party
    /// packages the pipeline needs? Returns nil when everything is present,
    /// otherwise the missing module list.
    public static func missingPythonPackages(engine: OrthoEngine) -> [String]? {
        // Frozen engines carry their whole runtime — nothing can be missing.
        guard !engine.isFrozen else { return nil }
        let probe = """
        import importlib, json, sys
        missing = []
        for mod in ("numpy", "PIL", "requests", "pyproj", "shapely", "rtree", "skfmm"):
            try:
                importlib.import_module(mod)
            except Exception:
                missing.append(mod)
        sys.stdout.write(json.dumps(missing))
        """
        let process = Process()
        process.executableURL = engine.pythonURL
        process.arguments = ["-c", probe]
        process.environment = OrthoProcessRunner.environment()
        let out = Pipe()
        process.standardOutput = out
        process.standardError = Pipe()
        do {
            try process.run()
        } catch {
            return ["python3"]
        }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0,
              let missing = try? JSONDecoder().decode([String].self, from: data)
        else { return ["python3"] }
        return missing.isEmpty ? nil : missing
    }
}
