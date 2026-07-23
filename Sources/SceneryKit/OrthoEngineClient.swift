import Foundation
import Darwin

/// A JSON value as it appears on the engine protocol wire. Command results
/// (tile info, config registry, link statuses) keep their full shape here
/// and callers pick out what they need.
public enum O4JSON: Sendable, Equatable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([O4JSON])
    case object([String: O4JSON])

    public static func from(_ any: Any) -> O4JSON {
        switch any {
        case is NSNull: return .null
        case let n as NSNumber:
            // NSNumber collapses bools and numbers; CFBoolean detection
            // keeps true/false from becoming 1/0.
            if CFGetTypeID(n) == CFBooleanGetTypeID() { return .bool(n.boolValue) }
            if let i = Int(exactly: n) { return .int(i) }
            return .double(n.doubleValue)
        case let s as String: return .string(s)
        case let a as [Any]: return .array(a.map { O4JSON.from($0) })
        case let d as [String: Any]:
            return .object(d.mapValues { O4JSON.from($0) })
        default: return .string(String(describing: any))
        }
    }

    public var stringValue: String? { if case .string(let s) = self { return s }; return nil }
    public var boolValue: Bool? { if case .bool(let b) = self { return b }; return nil }
    public var intValue: Int? {
        switch self {
        case .int(let i): return i
        case .double(let d): return Int(d)
        default: return nil
        }
    }
    public var doubleValue: Double? {
        switch self {
        case .double(let d): return d
        case .int(let i): return Double(i)
        default: return nil
        }
    }
    public var arrayValue: [O4JSON]? { if case .array(let a) = self { return a }; return nil }
    public var objectValue: [String: O4JSON]? { if case .object(let o) = self { return o }; return nil }

    public subscript(key: String) -> O4JSON? { objectValue?[key] }
}

/// Typed mirror of the engine protocol's event stream
/// (docs/specs/engine-protocol-multi-gui.md §5; src/o4_engine/events.py is
/// the schema). Unknown event types and fields are ignored by protocol rule.
public enum O4Event: Sendable, Equatable {
    case hello(engineVersion: String, protocolVersion: String, capabilities: [String])
    case log(level: String, text: String)
    case scanProgress(phase: String, done: Int, total: Int)
    /// built: [lat, lon, info] triples; installed: [lat, lon] pairs.
    case scanBatch(built: [(lat: Int, lon: Int, info: O4JSON)], installed: [(lat: Int, lon: Int)])
    case scanDone(builtCount: Int, installedCount: Int)
    case tileState(lat: Int, lon: Int, state: String, label: String, percent: Double)
    case stepProgress(lat: Int, lon: Int, stepKey: String, label: String,
                      percent: Double, indeterminate: Bool)
    case autoPatchBegin(airports: [String], lat: Int, lon: Int)
    case autoPatchProgress(airport: String, done: Double, total: Double, label: String,
                           status: String, etaTotalSeconds: Double?, lat: Int, lon: Int)
    case buildDone(lat: Int, lon: Int, ok: Bool, error: String)
    case runEta(elapsedSeconds: Double, remainingSeconds: Double?, doneTiles: Int, totalTiles: Int)
    case runDone(doneCount: Int, errorCount: Int, cancelled: Bool)
    case engineError(fatal: Bool, text: String)
    /// The engine's stderr: pipeline prints, initialization chatter — the
    /// raw console text that used to be stdout.
    case stderr(String)
    case unknown(event: String)

    public static func == (lhs: O4Event, rhs: O4Event) -> Bool {
        // Only scanBatch needs help (tuples aren't Equatable-synthesizable);
        // compare via a canonical description.
        String(describing: lhs) == String(describing: rhs)
    }

    /// Decode one stdout protocol line's event payload. Returns nil for
    /// reply lines (routed separately) and non-JSON lines.
    static func parse(object: [String: Any]) -> O4Event? {
        guard let type = object["event"] as? String else { return nil }
        func int(_ key: String) -> Int { (object[key] as? NSNumber)?.intValue ?? 0 }
        func double(_ key: String) -> Double { (object[key] as? NSNumber)?.doubleValue ?? 0 }
        func string(_ key: String) -> String { object[key] as? String ?? "" }
        func bool(_ key: String) -> Bool { (object[key] as? NSNumber)?.boolValue ?? false }

        switch type {
        case "EngineHello":
            return .hello(engineVersion: string("ortho4xp_version"),
                          protocolVersion: string("protocol"),
                          capabilities: (object["capabilities"] as? [Any])?
                              .compactMap { $0 as? String } ?? [])
        case "Log":
            return .log(level: string("level"), text: string("text"))
        case "ScanProgress":
            return .scanProgress(phase: string("phase"), done: int("done"), total: int("total"))
        case "ScanBatch":
            var built: [(lat: Int, lon: Int, info: O4JSON)] = []
            for entry in object["built"] as? [[Any]] ?? [] where entry.count >= 3 {
                guard let lat = (entry[0] as? NSNumber)?.intValue,
                      let lon = (entry[1] as? NSNumber)?.intValue else { continue }
                built.append((lat, lon, O4JSON.from(entry[2])))
            }
            var installed: [(lat: Int, lon: Int)] = []
            for entry in object["installed"] as? [[Any]] ?? [] where entry.count >= 2 {
                guard let lat = (entry[0] as? NSNumber)?.intValue,
                      let lon = (entry[1] as? NSNumber)?.intValue else { continue }
                installed.append((lat, lon))
            }
            return .scanBatch(built: built, installed: installed)
        case "ScanDone":
            return .scanDone(builtCount: int("built_count"), installedCount: int("installed_count"))
        case "TileState":
            return .tileState(lat: int("lat"), lon: int("lon"), state: string("state"),
                              label: string("label"), percent: double("percent"))
        case "StepProgress":
            return .stepProgress(lat: int("lat"), lon: int("lon"), stepKey: string("step_key"),
                                 label: string("label"), percent: double("percent"),
                                 indeterminate: bool("indeterminate"))
        case "AutoPatchBegin":
            return .autoPatchBegin(
                airports: (object["airports"] as? [Any])?.compactMap { $0 as? String } ?? [],
                lat: int("lat"), lon: int("lon"))
        case "AutoPatchProgress":
            let eta = (object["eta_total_seconds"] as? NSNumber)?.doubleValue
            return .autoPatchProgress(airport: string("airport"), done: double("done"),
                                      total: double("total"), label: string("label"),
                                      status: string("status"), etaTotalSeconds: eta,
                                      lat: int("lat"), lon: int("lon"))
        case "BuildDone":
            return .buildDone(lat: int("lat"), lon: int("lon"),
                              ok: bool("ok"), error: string("error"))
        case "RunEta":
            let remaining = (object["remaining_seconds"] as? NSNumber)?.doubleValue
            return .runEta(elapsedSeconds: double("elapsed_seconds"),
                           remainingSeconds: remaining,
                           doneTiles: int("done_tiles"), totalTiles: int("total_tiles"))
        case "RunDone":
            return .runDone(doneCount: int("done_count"), errorCount: int("error_count"),
                            cancelled: bool("cancelled"))
        case "Error":
            return .engineError(fatal: bool("fatal"), text: string("text"))
        default:
            return .unknown(event: type)
        }
    }
}

/// A command's reply line: {"reply": id, "ok": ..., "result"/"error": ...}.
public struct O4Reply: Sendable {
    public let ok: Bool
    public let result: O4JSON?
    public let error: String?
}

/// A built tile as the engine's scanner reports it (O4_Tile_Info.TileInfo,
/// delivered in ScanBatch.built triples and tile_info replies).
public struct O4TileInfo: Sendable, Equatable, Codable {
    public let lat: Int
    public let lon: Int
    public let buildDir: String
    public let dsfPresent: Bool
    public let provider: String
    public let zl: Int?
    public let hasZones: Bool
    public let customDEM: String
    /// Epoch seconds; nil when unknown.
    public let meshDate: Double?
    public let imageryDate: Double?
    public let sizeBytes: Int?

    public init?(json: O4JSON) {
        guard let object = json.objectValue,
              let lat = object["lat"]?.intValue,
              let lon = object["lon"]?.intValue else { return nil }
        self.lat = lat
        self.lon = lon
        buildDir = object["build_dir"]?.stringValue ?? ""
        dsfPresent = object["dsf_present"]?.boolValue ?? false
        provider = object["provider"]?.stringValue ?? ""
        zl = object["zl"]?.intValue
        hasZones = object["has_zones"]?.boolValue ?? false
        customDEM = object["custom_dem"]?.stringValue ?? ""
        meshDate = object["mesh_date"]?.doubleValue
        imageryDate = object["imagery_date"]?.doubleValue
        sizeBytes = object["size_bytes"]?.intValue
    }
}

/// The install-link state vocabulary (O4_Scenery_Links.LinkStatus values).
public enum O4LinkStatus: String, Sendable {
    case installed, physical, notInstalled = "not_installed"
    case broken, conflict, unavailable
}

/// Client for the engine's JSON-lines transport: spawns
/// `Ortho4XP.py --engine-jsonl` (one persistent process per session),
/// streams typed events, and correlates command replies by id. This is the
/// Doctor Builder view the engine protocol spec plans for; engines without
/// the protocol fall back to the legacy per-tile driver (OrthoBuildRunner).
public final class OrthoEngineClient: @unchecked Sendable {
    private let process = Process()
    private let stdinPipe = Pipe()
    private let stdoutPipe = Pipe()
    private let stderrPipe = Pipe()

    private let lock = NSLock()
    private var stdoutBuffer = Data()
    private var stderrBuffer = Data()
    private var nextID = 1
    private var pendingReplies: [Int: @Sendable (O4Reply) -> Void] = [:]

    private let onEvent: @Sendable (O4Event) -> Void
    private let onExit: @Sendable (Int32) -> Void

    /// Does this engine ship the JSON-lines transport? Frozen engines are
    /// built from the dev branch and always do.
    public static func engineSupportsProtocol(_ engine: OrthoEngine) -> Bool {
        engine.isFrozen || FileManager.default.fileExists(
            atPath: engine.root.appendingPathComponent("src/o4_engine/jsonl.py").path)
    }

    public init(onEvent: @escaping @Sendable (O4Event) -> Void,
                onExit: @escaping @Sendable (Int32) -> Void) {
        self.onEvent = onEvent
        self.onExit = onExit
    }

    public var isRunning: Bool { process.isRunning }

    public func launch(engine: OrthoEngine) throws {
        if let frozen = engine.frozenExecutableURL {
            // Self-contained engine: its own Python runtime is inside.
            process.executableURL = frozen
            process.arguments = ["--engine-jsonl"]
        } else {
            process.executableURL = engine.pythonURL
            process.arguments = ["-u", engine.root.appendingPathComponent("Ortho4XP.py").path,
                                 "--engine-jsonl"]
        }
        process.currentDirectoryURL = engine.root
        var env = OrthoProcessRunner.environment()
        // Arms the engine's parent-death watchdog: if this app dies, the
        // engine red-flags any build and exits instead of going headless.
        env["O4_PARENT_PROCESS_ID"] = String(ProcessInfo.processInfo.processIdentifier)
        process.environment = env
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        stdoutPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            self?.consumeStdout(data)
        }
        stderrPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            self?.consumeStderr(data)
        }
        process.terminationHandler = { [weak self] proc in
            guard let self else { return }
            // Fail any commands still awaiting replies.
            let waiting = self.lock.withLock {
                let handlers = self.pendingReplies.values
                self.pendingReplies = [:]
                return Array(handlers)
            }
            for handler in waiting {
                handler(O4Reply(ok: false, result: nil, error: "engine exited"))
            }
            self.onExit(proc.terminationStatus)
        }
        try process.run()
    }

    /// Send a command; the completion receives the correlated reply.
    /// Events the command triggers arrive through onEvent as usual.
    public func send(command: String, arguments: [String: Any] = [:],
                     completion: (@Sendable (O4Reply) -> Void)? = nil) {
        var message: [String: Any] = ["cmd": command]
        let id: Int = lock.withLock {
            let id = nextID
            nextID += 1
            if let completion { pendingReplies[id] = completion }
            return id
        }
        message["id"] = id
        for (key, value) in arguments { message[key] = value }
        guard let data = try? JSONSerialization.data(withJSONObject: message),
              process.isRunning else {
            _ = lock.withLock { pendingReplies.removeValue(forKey: id) }
            completion?(O4Reply(ok: false, result: nil, error: "engine not running"))
            return
        }
        stdinPipe.fileHandleForWriting.write(data + Data("\n".utf8))
    }

    /// Graceful shutdown: the engine red-flags any in-flight build and
    /// exits within its bounded grace window. Closing stdin afterwards
    /// covers an engine that never saw the command.
    public func shutdown() {
        send(command: "shutdown")
        try? stdinPipe.fileHandleForWriting.close()
    }

    public func terminate() {
        guard process.isRunning else { return }
        process.terminate() // SIGTERM: engine routes it through the same bounded stop
    }

    public func kill() {
        guard process.isRunning else { return }
        Darwin.kill(process.processIdentifier, SIGKILL)
    }

    // MARK: - Stream handling

    private func consumeStdout(_ data: Data) {
        for line in splitLines(&stdoutBuffer, appending: data) {
            handleProtocolLine(line)
        }
    }

    private func consumeStderr(_ data: Data) {
        for line in splitLines(&stderrBuffer, appending: data) where !line.isEmpty {
            onEvent(.stderr(line))
        }
    }

    private func splitLines(_ buffer: inout Data, appending data: Data) -> [String] {
        lock.lock()
        buffer.append(data)
        var lines: [String] = []
        while let nl = buffer.firstIndex(of: UInt8(ascii: "\n")) {
            let lineData = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            lines.append(String(decoding: lineData, as: UTF8.self))
        }
        lock.unlock()
        return lines
    }

    private func handleProtocolLine(_ line: String) {
        guard !line.isEmpty,
              let object = (try? JSONSerialization.jsonObject(with: Data(line.utf8))) as? [String: Any]
        else { return }
        if let replyID = (object["reply"] as? NSNumber)?.intValue {
            let handler = lock.withLock { pendingReplies.removeValue(forKey: replyID) }
            handler?(O4Reply(
                ok: (object["ok"] as? NSNumber)?.boolValue ?? false,
                result: object["result"].map { O4JSON.from($0) },
                error: object["error"] as? String))
            return
        }
        if let event = O4Event.parse(object: object) {
            onEvent(event)
        }
    }
}
