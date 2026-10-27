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

/// One tile's clock row from a `TileClocks` event (protocol 1.3).
public struct O4TileClock: Sendable, Equatable {
    public let lat: Int
    public let lon: Int
    public let elapsedSeconds: Double
    public let remainingSeconds: Double?
    public let finished: Bool

    public init(lat: Int, lon: Int, elapsedSeconds: Double,
                remainingSeconds: Double?, finished: Bool) {
        self.lat = lat
        self.lon = lon
        self.elapsedSeconds = elapsedSeconds
        self.remainingSeconds = remainingSeconds
        self.finished = finished
    }
}

/// One provider account the engine can sign into, as the `auth_providers`
/// command describes it (protocol 1.5). Several provider codes may share
/// one account, so this is per SESSION, not per provider.
///
/// The status fields are derived from LOCAL state only — the engine never
/// probes the network to build this, exactly as the Qt settings section
/// doesn't.
public struct O4ProviderAccount: Sendable, Equatable, Identifiable {
    public var id: String { sessionName }
    public let sessionName: String
    /// Provider codes sharing this account (e.g. PORTUGAL2M, PORTUGALTIDAL).
    public let codes: [String]
    public let attribution: String
    /// "session" | "http_basic" | "api_key".
    public let credentialKind: String
    public let loginURL: String
    public let registrationURL: String
    public let serviceHost: String
    public let setupSteps: [String]
    public let credentialStoreAvailable: Bool
    public let signedIn: Bool
    public let username: String
    /// The status line, in the engine's own vocabulary ("Signed in as …",
    /// "Session saved", "Not signed in", "API key stored", "No API key").
    public let statusText: String
    /// The store-derived status is still being read off the engine's
    /// command thread: what is here may be stale, ask again shortly.
    public let statusPending: Bool

    /// One secret string IS the whole credential: no username, and it only
    /// works stored (it is read back at build time).
    public var isAPIKey: Bool { credentialKind == "api_key" }
    /// Row title: the service's own attribution, else the account name.
    public var title: String { attribution.isEmpty ? sessionName : attribution }
    /// Sheet title: the attribution, else the service host.
    public var sheetTitle: String { attribution.isEmpty ? serviceHost : attribution }

    public init?(json: O4JSON) {
        guard let object = json.objectValue,
              let sessionName = object["session_name"]?.stringValue
        else { return nil }
        self.sessionName = sessionName
        codes = object["codes"]?.arrayValue?.compactMap { $0.stringValue } ?? []
        attribution = object["attribution"]?.stringValue ?? ""
        credentialKind = object["credential_kind"]?.stringValue ?? "session"
        loginURL = object["login_url"]?.stringValue ?? ""
        registrationURL = object["registration_url"]?.stringValue ?? ""
        serviceHost = object["service_host"]?.stringValue ?? ""
        setupSteps = object["setup_steps"]?.arrayValue?.compactMap { $0.stringValue } ?? []
        credentialStoreAvailable = object["credential_store_available"]?.boolValue ?? false
        signedIn = object["signed_in"]?.boolValue ?? false
        username = object["username"]?.stringValue ?? ""
        statusText = object["status_text"]?.stringValue ?? ""
        statusPending = object["status_pending"]?.boolValue ?? false
    }
}

/// The `airport_index` command's reply (protocol 1.6).
///
/// `status` is the engine's own vocabulary: "ready" (read the TSV at
/// `path`; `count` airports), "building" (a rebuild started — the
/// `airportIndexReady` event carries the path when it lands), or "none"
/// (no X-Plane folder, or it ships no Global Airports apt.dat).
public struct O4AirportIndexReply: Sendable, Equatable {
    public let status: String
    public let path: String
    public let count: Int

    public var isReady: Bool { status == "ready" }
    public var isBuilding: Bool { status == "building" }
}

/// One 1°×1° cell as the boundary preflight names it (protocol 1.8).
/// The wire carries `[lat, lon]` pairs; this is their typed form.
public struct O4TileRef: Sendable, Equatable, Hashable, Codable {
    public let lat: Int
    public let lon: Int

    public init(lat: Int, lon: Int) {
        self.lat = lat
        self.lon = lon
    }

    /// "+38-009" — the tile name the user sees on the map.
    public var key: String { TileMath.key(lat: lat, lon: lon) }

    /// Decode one `[lat, lon]` wire pair.
    public static func from(_ any: Any) -> O4TileRef? {
        guard let pair = any as? [Any], pair.count >= 2,
              let lat = (pair[0] as? NSNumber)?.intValue,
              let lon = (pair[1] as? NSNumber)?.intValue else { return nil }
        return O4TileRef(lat: lat, lon: lon)
    }
}

/// One airport whose AIRSIDE claim reaches into a 1° cell this build is not
/// building (protocol 1.8, spec insets-follow-patch-set-spec.md §C.2). Only
/// class-S airports are ever listed: a groundside / inset-box / DEM-window
/// crosser (class M) never prompts (owner RULINGS 2026-09-18h).
public struct O4BoundaryAirport: Sendable, Equatable, Identifiable {
    public var id: String { icao }
    public let icao: String
    public let name: String
    /// The cell the airport belongs to.
    public let home: O4TileRef
    /// The COLD cells its claim reaches into (warm ones are not listed).
    public let neighbours: [O4TileRef]
    /// How far the claim reaches past the tile line, in metres.
    public let crossingMeters: Double

    public init(icao: String, name: String, home: O4TileRef,
                neighbours: [O4TileRef], crossingMeters: Double) {
        self.icao = icao
        self.name = name
        self.home = home
        self.neighbours = neighbours
        self.crossingMeters = crossingMeters
    }

    public init?(json: Any) {
        guard let object = json as? [String: Any],
              let icao = object["icao"] as? String else { return nil }
        self.icao = icao
        name = object["name"] as? String ?? ""
        home = (object["home"].flatMap { O4TileRef.from($0) })
            ?? O4TileRef(lat: 0, lon: 0)
        neighbours = (object["neighbours"] as? [Any])?
            .compactMap { O4TileRef.from($0) } ?? []
        crossingMeters = (object["crossing_m"] as? NSNumber)?.doubleValue ?? 0
    }
}

/// The boundary preflight's completion (`BoundaryAirportsReady`, protocol
/// 1.8) — the second half of a `boundary_airports` command, which replies
/// `{"status": "started", "request_id": N}` at once and works on an engine
/// worker thread.
public struct O4BoundaryAirportsReady: Sendable, Equatable {
    public let requestID: Int
    /// Empty ⇒ proceed straight to `enqueue_build`, no dialog.
    public let airports: [O4BoundaryAirport]
    /// The COMPLETE, deduplicated set of cold neighbour cells every listed
    /// airport needs and that were not already requested, sorted.
    public let addTiles: [O4TileRef]
    /// "" | "neighbour" | "skip" — the saved `auto_patch_boundary` answer;
    /// non-empty means apply it without asking.
    public let remembered: String
    /// The preflight's failure text; non-empty ⇒ proceed with a nil policy.
    public let error: String
    /// The policy the dialog PRESELECTS (its Return-key action), engine-owned
    /// so the two front ends cannot spell the default differently
    /// (owner RULINGS 2026-09-18i (2)). NOT the unattended default.
    public let defaultChoice: String

    public init(requestID: Int, airports: [O4BoundaryAirport],
                addTiles: [O4TileRef], remembered: String,
                error: String, defaultChoice: String) {
        self.requestID = requestID
        self.airports = airports
        self.addTiles = addTiles
        self.remembered = remembered
        self.error = error
        self.defaultChoice = defaultChoice
    }
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
    /// `detail` (additive within protocol 1.10, #598): whole sentences for
    /// a second line under the tile's row — for a stopped tile, what it is
    /// left with. Empty from an older engine; shown verbatim.
    /// `attempt` (additive within protocol 1.14, #1326): which admission of
    /// the tile the event belongs to, so a stopped attempt's late news is
    /// told apart from the attempt that re-queued the tile. 0 = unknown.
    case tileState(lat: Int, lon: Int, state: String, label: String, percent: Double,
                   detail: String = "", attempt: Int = 0)
    case stepProgress(lat: Int, lon: Int, stepKey: String, label: String,
                      percent: Double, indeterminate: Bool, attempt: Int = 0)
    case autoPatchBegin(airports: [String], lat: Int, lon: Int)
    case autoPatchProgress(airport: String, done: Double, total: Double, label: String,
                           status: String, etaTotalSeconds: Double?, lat: Int, lon: Int)
    /// One airport's auto-patch build FAILED and the tile build is aborting
    /// (engine `AutoPatchFailed`). Distinct from `autoPatchProgress(status:
    /// "fail")`, which is only that airport's row state: this carries the
    /// diagnosis — which airport, which `stage` (`build`/`write`/`worker`/
    /// `missing`/`manifest`) and the cause. A `buildDone(ok: false)` for the
    /// tile follows, its `error` naming the same airports.
    ///
    /// Added for H1 (Ortho4XP/docs/POSTMORTEM-20260831.md Task C): before it
    /// a per-airport death reached only the engine console, the tile finished
    /// with exit 0 and the previous build's scenery flew.
    ///
    /// `code` (protocol 1.10, #562) is the engine's failure class; `error`
    /// is technical detail, and the user's message arrives on the tile's
    /// `buildDone` (`failures`, or `warnings` when the tile is still built
    /// — owner RULINGS 2026-10-12a, #564).
    case autoPatchFailed(airport: String, stage: String, error: String, lat: Int, lon: Int,
                         code: String)
    /// One tile finished. `failures` (protocol 1.10) say why it was NOT
    /// built; `warnings` name airports without a patch on a tile that was
    /// built ("built with warnings"), folded per cause;
    /// `unpatchedAirports` are the same airports one per entry. `error` is
    /// the failures as one line.
    /// `notes` are info-level entries of a built tile (stand-in
    /// elevation, owner RULINGS 2026-10-12e), shown under the warnings.
    case buildDone(lat: Int, lon: Int, ok: Bool, error: String,
                   failures: [O4TileFailure], warnings: [O4TileFailure],
                   unpatchedAirports: [O4TileFailure], notes: [O4TileFailure])
    /// A tile's imagery DOWNLOAD queue drained; only the local texture
    /// conversion remains (engine `ImageryDownloadsDone`). A scheduling
    /// signal for the engine's own orchestrator; the app shows nothing.
    case imageryDownloadsDone(lat: Int, lon: Int, downloaded: Int, failed: Int)
    case runEta(elapsedSeconds: Double, remainingSeconds: Double?, doneTiles: Int, totalTiles: Int)
    /// Per-tile clocks beside RunEta (protocol 1.3): each row is one
    /// tile's elapsed wall time and its OWN remaining-work estimate
    /// (nil = no defensible basis; views show a dash, never a guess).
    case tileClocks(rows: [O4TileClock])
    case runDone(doneCount: Int, errorCount: Int, cancelled: Bool)
    /// The engine asks the app to service one secret-store operation from
    /// the app's own Keychain (credential broker; answer with a
    /// `secret_response` command carrying the same requestID).
    case secretRequest(requestID: Int, operation: String, sessionName: String,
                       account: String, secret: String)
    /// A `provider_sign_in` / `provider_sign_out` attempt finished
    /// (protocol 1.5). Both commands reply `{"started": true}` at once and
    /// work on an engine worker thread — they touch the brokered secret
    /// store, which the engine's own command thread may not do.
    /// `errorText` is the failure message, ready to show.
    case signInResult(sessionName: String, ok: Bool, errorText: String)
    /// The Global Airports index finished (re)building (protocol 1.6) —
    /// the completion half of an `airport_index` command that replied
    /// "building". `path` is the TSV cache to read (empty on failure) and
    /// `error` the engine's failure text.
    case airportIndexReady(path: String, count: Int, error: String)
    /// The boundary-airport preflight finished (protocol 1.8) — the
    /// completion half of a `boundary_airports` command. Correlate on
    /// `requestID`; ignore the rest.
    case boundaryAirportsReady(O4BoundaryAirportsReady)
    /// A scenery pack X-Plane will not load (protocol 1.9, #433): found by
    /// the object stage, or the completion of an `omit_missing_art`
    /// command. See `O4PackMissingArt`.
    case packMissingArt(O4PackMissingArt)
    /// One imagery source's launch-time liveness (protocol 1.17, #1345):
    /// the completion of `imagery_source_status`, one event per source.
    case imagerySourceStatus(code: String, status: O4ImageryStatus)
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
                              label: string("label"), percent: double("percent"),
                              detail: string("detail"), attempt: int("attempt"))
        case "StepProgress":
            return .stepProgress(lat: int("lat"), lon: int("lon"), stepKey: string("step_key"),
                                 label: string("label"), percent: double("percent"),
                                 indeterminate: bool("indeterminate"), attempt: int("attempt"))
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
        // The event name is matched here as a STRING LITERAL and never
        // appears in Python source: it is `class AutoPatchFailed` in
        // Ortho4XP/src/o4_engine/events.py. Renaming either side breaks the
        // other silently (see CLAUDE.md, "Cross-language wire protocol").
        case "AutoPatchFailed":
            return .autoPatchFailed(airport: string("airport"), stage: string("stage"),
                                    error: string("error"),
                                    lat: int("lat"), lon: int("lon"),
                                    code: string("code"))
        case "BuildDone":
            return .buildDone(lat: int("lat"), lon: int("lon"),
                              ok: bool("ok"), error: string("error"),
                              failures: O4TileFailure.parseList(object["failures"]),
                              warnings: O4TileFailure.parseList(
                                  object["warnings"], defaultSeverity: "degraded"),
                              unpatchedAirports: O4TileFailure.parseList(
                                  object["unpatched_airports"], defaultSeverity: "degraded"),
                              notes: O4TileFailure.parseList(
                                  object["notes"], defaultSeverity: "info"))
        // Another STRING LITERAL match: `class ImageryDownloadsDone` in
        // Ortho4XP/src/o4_engine/events.py — a tile's imagery downloads
        // drained, only the local conversion remains (a scheduling signal).
        case "ImageryDownloadsDone":
            return .imageryDownloadsDone(lat: int("lat"), lon: int("lon"),
                                         downloaded: int("downloaded"),
                                         failed: int("failed"))
        case "RunEta":
            let remaining = (object["remaining_seconds"] as? NSNumber)?.doubleValue
            return .runEta(elapsedSeconds: double("elapsed_seconds"),
                           remainingSeconds: remaining,
                           doneTiles: int("done_tiles"), totalTiles: int("total_tiles"))
        case "TileClocks":
            // Rows are positional [lat, lon, elapsed, remaining|null, finished].
            var rows: [O4TileClock] = []
            for entry in object["rows"] as? [[Any]] ?? [] where entry.count >= 5 {
                guard let lat = (entry[0] as? NSNumber)?.intValue,
                      let lon = (entry[1] as? NSNumber)?.intValue else { continue }
                rows.append(O4TileClock(
                    lat: lat, lon: lon,
                    elapsedSeconds: (entry[2] as? NSNumber)?.doubleValue ?? 0,
                    remainingSeconds: (entry[3] as? NSNumber)?.doubleValue,
                    finished: (entry[4] as? NSNumber)?.boolValue ?? false))
            }
            return .tileClocks(rows: rows)
        case "RunDone":
            return .runDone(doneCount: int("done_count"), errorCount: int("error_count"),
                            cancelled: bool("cancelled"))
        case "SecretRequest":
            return .secretRequest(requestID: int("request_id"), operation: string("operation"),
                                  sessionName: string("session_name"),
                                  account: string("account"), secret: string("secret"))
        case "SignInResult":
            return .signInResult(sessionName: string("session_name"),
                                 ok: bool("ok"), errorText: string("error_text"))
        case "AirportIndexReady":
            return .airportIndexReady(path: string("path"), count: int("count"),
                                      error: string("error"))
        // Another STRING LITERAL match (see AutoPatchFailed above): it is
        // `class BoundaryAirportsReady` in Ortho4XP/src/o4_engine/events.py
        // and the name never appears in Python source.
        case "BoundaryAirportsReady":
            return .boundaryAirportsReady(O4BoundaryAirportsReady(
                requestID: int("request_id"),
                airports: (object["airports"] as? [Any])?
                    .compactMap { O4BoundaryAirport(json: $0) } ?? [],
                addTiles: (object["add_tiles"] as? [Any])?
                    .compactMap { O4TileRef.from($0) } ?? [],
                remembered: string("remembered"),
                error: string("error"),
                // An engine that predates default_choice still preselects
                // the owner's default (RULINGS 2026-09-18i (2)).
                defaultChoice: object["default_choice"] as? String ?? "neighbour"))
        // Another STRING LITERAL match (see AutoPatchFailed above): it is
        // `class PackMissingArt` in Ortho4XP/src/o4_engine/events.py.
        case "PackMissingArt":
            var kinds: [String: Int] = [:]
            for (key, value) in object["kinds"] as? [String: Any] ?? [:] {
                if let n = (value as? NSNumber)?.intValue { kinds[key] = n }
            }
            return .packMissingArt(O4PackMissingArt(
                pack: string("pack"), packRoot: string("pack_root"),
                lat: int("lat"), lon: int("lon"), total: int("total"),
                kinds: kinds, uses: int("uses"),
                firstPaths: (object["first_paths"] as? [Any])?
                    .compactMap { $0 as? String } ?? [],
                // absent ⇒ no primary button: never offer without a yes
                canOmit: bool("can_omit"),
                state: object["state"] as? String ?? "found",
                error: string("error")))
        // Another STRING LITERAL match (see AutoPatchFailed above): it is
        // `class ImagerySourceStatus` in Ortho4XP/src/o4_engine/events.py.
        case "ImagerySourceStatus":
            return .imagerySourceStatus(
                code: string("code"),
                status: O4ImageryStatus(status: object["status"] as? String ?? "unknown",
                                        reason: string("reason")))
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
    /// cover_airports_with_highres from the tile cfg ("" or "False" = off;
    /// "True", "ICAO" or "Existing" = airports upgraded to coverZL).
    public let highZLAirports: String
    public let coverZL: Int?
    public let customDEM: String
    /// Epoch seconds; nil when unknown.
    public let meshDate: Double?
    public let imageryDate: Double?
    public let sizeBytes: Int?
    /// The imagery the tile's textures carry (#1334): the dominant
    /// provider among `textures/` names and its ZL; nil when none parses
    /// (or the engine predates the field). `TileImageryChoice.resolve`
    /// picks the cfg's or this.
    public let detectedProvider: String?
    public let detectedZL: Int?

    public init?(json: O4JSON) {
        guard let object = json.objectValue,
              let lat = object["lat"]?.intValue,
              let lon = object["lon"]?.intValue else { return nil }
        // Legacy tile configs quote string values (default_website='Arc');
        // older engines pass the quotes through — strip them here so
        // display and imagery-source comparisons see the bare value.
        func unquoted(_ value: String) -> String {
            guard value.count >= 2, let first = value.first,
                  first == value.last, first == "'" || first == "\""
            else { return value }
            return String(value.dropFirst().dropLast())
        }
        self.lat = lat
        self.lon = lon
        buildDir = object["build_dir"]?.stringValue ?? ""
        dsfPresent = object["dsf_present"]?.boolValue ?? false
        provider = unquoted(object["provider"]?.stringValue ?? "")
        zl = object["zl"]?.intValue
        hasZones = object["has_zones"]?.boolValue ?? false
        highZLAirports = unquoted(object["high_zl_airports"]?.stringValue ?? "")
        coverZL = object["cover_zl"]?.intValue
        customDEM = unquoted(object["custom_dem"]?.stringValue ?? "")
        meshDate = object["mesh_date"]?.doubleValue
        imageryDate = object["imagery_date"]?.doubleValue
        sizeBytes = object["size_bytes"]?.intValue
        detectedProvider = object["detected_provider"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 }
        detectedZL = object["detected_zl"]?.intValue
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
    private var stdoutLines = LineSplitter()
    private var stderrLines = LineSplitter()
    private var nextID = 1
    private var pendingReplies: [Int: @Sendable (O4Reply) -> Void] = [:]
    /// Commands completed by an EVENT naming their id (`request`), keyed by
    /// that id: the event goes to its waiter, never to `onEvent`. nil =
    /// the engine exited first.
    private var eventWaiters: [Int: @Sendable (O4JSON?) -> Void] = [:]

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
            let eventWaiters = self.lock.withLock {
                defer { self.eventWaiters = [:] }
                return Array(self.eventWaiters.values)
            }
            for handler in waiting {
                handler(O4Reply(ok: false, result: nil, error: "engine exited"))
            }
            for waiter in eventWaiters { waiter(nil) }
            self.onExit(proc.terminationStatus)
        }
        // Normal QoS (owner RULINGS 2026-10-22k, amending #1225): utility
        // confined the engine and its workers to the efficiency cores. The
        // engine's nice 10, slot budget and memory gate keep the Mac usable.
        process.qualityOfService = .default
        try process.run()
    }

    /// Send a command; the completion receives the correlated reply.
    /// Events the command triggers arrive through onEvent as usual.
    public func send(command: String, arguments: [String: Any] = [:],
                     completion: (@Sendable (O4Reply) -> Void)? = nil) {
        send(command: command, arguments: arguments, completion: completion, completionEvent: nil)
    }

    /// `send`, for a command an EVENT completes: `completionEvent` receives
    /// that event's JSON (registered before the line is written, so an
    /// event that beats the reply is not lost). An `ok: false` reply
    /// removes the waiter; the reply completion reports the error.
    func send(command: String, arguments: [String: Any],
              completion: (@Sendable (O4Reply) -> Void)?,
              completionEvent: (@Sendable (O4JSON?) -> Void)?) {
        var message: [String: Any] = ["cmd": command]
        let id: Int = lock.withLock {
            let id = nextID
            nextID += 1
            if let completion { pendingReplies[id] = completion }
            if let completionEvent { eventWaiters[id] = completionEvent }
            return id
        }
        message["id"] = id
        for (key, value) in arguments { message[key] = value }
        guard let data = try? JSONSerialization.data(withJSONObject: message),
              process.isRunning else {
            _ = lock.withLock {
                eventWaiters.removeValue(forKey: id)
                return pendingReplies.removeValue(forKey: id)
            }
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

    // MARK: - Provider accounts (protocol 1.5)

    /// Every provider account this engine can sign into, with the status it
    /// can know without touching the network. Empty when the engine
    /// predates the command (unknown commands reply ok=false).
    public func authProviders() async -> [O4ProviderAccount] {
        await withCheckedContinuation { continuation in
            send(command: "auth_providers") { reply in
                guard reply.ok, let rows = reply.result?.arrayValue else {
                    continuation.resume(returning: [])
                    return
                }
                continuation.resume(
                    returning: rows.compactMap { O4ProviderAccount(json: $0) })
            }
        }
    }

    /// Start one sign-in. Returns nil once the engine has STARTED it — the
    /// outcome arrives later as a `signInResult` event — or the engine's
    /// error text when the command itself was refused.
    ///
    /// `secret` is the password, or the whole credential for an api_key
    /// provider (whose `username` is empty). It travels the private stdio
    /// pipe to the engine and, with `remember`, back to this app's own
    /// Keychain as a brokered `SecretRequest` — this app writes provider
    /// credentials no other way.
    public func providerSignIn(sessionName: String, username: String,
                               secret: String, remember: Bool) async -> String? {
        await withCheckedContinuation { continuation in
            send(command: "provider_sign_in", arguments: [
                "session_name": sessionName, "username": username,
                "secret": secret, "remember": remember,
            ]) { reply in
                continuation.resume(returning: reply.ok
                                    ? nil : (reply.error ?? "unknown engine error"))
            }
        }
    }

    /// Forget one account: stored credentials, API key and saved session.
    /// Also completes through `signInResult` (the deletions are secret-store
    /// operations, so they run on an engine worker thread too).
    public func providerSignOut(sessionName: String) async -> String? {
        await withCheckedContinuation { continuation in
            send(command: "provider_sign_out",
                 arguments: ["session_name": sessionName]) { reply in
                continuation.resume(returning: reply.ok
                                    ? nil : (reply.error ?? "unknown engine error"))
            }
        }
    }

    // MARK: - Imagery sources (protocol 1.17, #1345)

    /// The engine's one imagery source list, in menu order. Empty when the
    /// engine predates the command (unknown commands reply ok=false).
    public func imagerySources() async -> [O4ImagerySource] {
        let result: Result<[O4ImagerySource], Error> = await withCheckedContinuation { continuation in
            send(command: "imagery_sources") { reply in
                continuation.resume(returning: Self.decodeReply(reply, command: "imagery_sources"))
            }
        }
        return (try? result.get()) ?? []
    }

    /// Start the background liveness check: one `imagerySourceStatus`
    /// event per source follows from engine worker threads.
    public func startImagerySourceStatus() {
        send(command: "imagery_source_status")
    }

    // MARK: - Default airport index (protocol 1.6)

    /// Ask the engine for X-Plane's Global Airports index. The engine owns
    /// the apt.dat parse (src/O4_Airport_Index.py) and answers with the TSV
    /// cache to read — this app never parses the 380 MB file itself.
    ///
    /// A "building" reply means the parse started on an engine worker
    /// thread; the `airportIndexReady` event completes it. Engines that
    /// predate the command reply ok=false and are reported as "none".
    public func requestAirportIndex(
        xplaneDir: String,
        completion: @escaping @Sendable (O4AirportIndexReply) -> Void
    ) {
        send(command: "airport_index", arguments: ["xplane_dir": xplaneDir]) { reply in
            guard reply.ok, let result = reply.result?.objectValue else {
                completion(O4AirportIndexReply(status: "none", path: "", count: 0))
                return
            }
            completion(O4AirportIndexReply(
                status: result["status"]?.stringValue ?? "none",
                path: result["path"]?.stringValue ?? "",
                count: result["count"]?.intValue ?? 0))
        }
    }

    // MARK: - Failure report (protocol 1.10, issue #565)

    /// One tile's redacted report (engine `o4_engine.failure_report`). The
    /// command name and keys are STRING LITERALS matched against
    /// `Ortho4XP/src/o4_engine/jsonl.py` / `failure_report.py`. A non-empty
    /// `savePath` also writes the report file there. `nil` on any failure.
    public func failureReport(
        lat: Int, lon: Int, failures: [O4TileFailure], appVersion: String,
        logPath: String, xplaneDir: String, savePath: String = "",
        completion: @escaping @Sendable (O4FailureReport?) -> Void
    ) {
        send(command: "failure_report", arguments: [
            "lat": lat, "lon": lon,
            "failures": failures.map(\.wireObject),
            "app_version": appVersion, "app_name": "mac",
            "log_path": logPath, "xplane_dir": xplaneDir,
            "save_path": savePath,
        ]) { reply in
            guard reply.ok, let result = reply.result?.objectValue else {
                completion(nil)
                return
            }
            completion(O4FailureReport(
                title: result["title"]?.stringValue ?? "",
                report: result["report"]?.stringValue ?? "",
                issueURL: result["issue_url"]?.stringValue ?? "",
                fileName: result["file_name"]?.stringValue ?? "",
                savedPath: result["saved_path"]?.stringValue ?? ""))
        }
    }

    // MARK: - Unmounted-drive link (protocol 1.11, issue #668)

    /// Remove ONE dangling link directly in a Custom Scenery folder
    /// (engine `O4_Unmounted_Links.remove_link`; the command name and key
    /// are STRING LITERALS matched against `o4_engine/jsonl.py`). The engine
    /// refuses a folder, a reachable link and a path outside Custom
    /// Scenery. The completion carries nil on success, else the reason.
    public func removeSceneryLink(
        path: String, completion: @escaping @Sendable (String?) -> Void
    ) {
        send(command: "remove_scenery_link", arguments: ["path": path]) { reply in
            completion(reply.ok ? nil : (reply.error ?? "The engine did not answer."))
        }
    }

    // MARK: - Boundary airports (protocol 1.8)

    /// Start the boundary-airport preflight for the tiles about to be
    /// enqueued. The completion carries the engine's `request_id` — the
    /// `boundaryAirportsReady` event with that id completes it.
    ///
    /// nil means the preflight never started: an engine older than 1.8
    /// (unknown commands reply ok=false), a dead engine, or a refusal. The
    /// caller then enqueues exactly as it did before 1.8.
    public func requestBoundaryAirports(
        tiles: [O4TileRef],
        completion: @escaping @Sendable (Int?) -> Void
    ) {
        send(command: "boundary_airports",
             arguments: ["tiles": tiles.map { [$0.lat, $0.lon] }]) { reply in
            guard reply.ok, let result = reply.result?.objectValue,
                  let requestID = result["request_id"]?.intValue else {
                completion(nil)
                return
            }
            completion(requestID)
        }
    }

    // MARK: - Missing art (protocol 1.9)

    /// The user accepted "Build without the missing items" for one pack's
    /// tile DSF (owner RULINGS 2026-10-06c, #433). The engine replies
    /// `{"status": "started"}` at once and completes with a
    /// `packMissingArt` event whose `state` is "omitted" / "failed" /
    /// "none". An engine older than 1.9 replies ok=false: nothing changes.
    public func omitMissingArt(packRoot: String, lat: Int, lon: Int) {
        send(command: "omit_missing_art",
             arguments: ["pack_root": packRoot, "lat": lat, "lon": lon])
    }

    // MARK: - Stream handling

    private func consumeStdout(_ data: Data) {
        for line in splitLines(&stdoutLines, appending: data) {
            handleProtocolLine(line)
        }
    }

    private func consumeStderr(_ data: Data) {
        for line in splitLines(&stderrLines, appending: data) where !line.isEmpty {
            onEvent(.stderr(line))
            EngineStderrLog.shared.append(line)
        }
    }

    /// Linear in the bytes received (LineSplitter): a 50 MB reply line no
    /// longer re-scans its own head on every 64 KB chunk (owner 1.0.398:
    /// a patch save queued behind a PackObjectsReady line at 99 % CPU).
    private func splitLines(_ splitter: inout LineSplitter, appending data: Data) -> [String] {
        lock.withLock { splitter.append(data) }
    }

    private func handleProtocolLine(_ line: String) {
        guard !line.isEmpty,
              let object = (try? JSONSerialization.jsonObject(with: Data(line.utf8))) as? [String: Any]
        else { return }
        if let replyID = (object["reply"] as? NSNumber)?.intValue {
            let ok = (object["ok"] as? NSNumber)?.boolValue ?? false
            let handler = lock.withLock {
                if !ok { eventWaiters.removeValue(forKey: replyID) }
                return pendingReplies.removeValue(forKey: replyID)
            }
            handler?(O4Reply(
                ok: (object["ok"] as? NSNumber)?.boolValue ?? false,
                result: object["result"].map { O4JSON.from($0) },
                error: object["error"] as? String))
            return
        }
        // A STRING LITERAL match (see O4Event.parse): these are `class
        // PackObjectsReady`, `class LibraryReady` and `class
        // PlanEstimateReady` in Ortho4XP/src/o4_engine/events.py, the
        // completions of the `pack_objects`, Library and `plan_estimate`
        // (#820) commands whose id is `request`.
        switch object["event"] as? String {
        case "PackObjectsReady", "LibraryReady", "PlanEstimateReady":
            if let request = (object["request"] as? NSNumber)?.intValue,
               let waiter = lock.withLock({ eventWaiters.removeValue(forKey: request) }) {
                waiter(O4JSON.from(object))
                return
            }
        default:
            break
        }
        if let event = O4Event.parse(object: object) {
            onEvent(event)
        }
    }
}

// MARK: - Patch editor (protocol 1.12, issue #46)

/// The eight commands of the patch-editor spec §2
/// (`Ortho4XP/docs/specs/patch-editor-20261015.md`). The command names and
/// argument keys are STRING LITERALS matched against `o4_engine/jsonl.py`.
/// Each throws `O4CommandError` carrying the engine's sentence on an
/// `ok: false` reply; an engine older than 1.12 answers "unknown command",
/// which callers gate on `O4ProtocolVersion.supportsPatchEditor` first.
/// Replies are decoded on the reader thread, never the main actor.
extension OrthoEngineClient {
    public func patchList(tile: String) async throws -> O4PatchList {
        try await request("patch_list", ["tile": tile])
    }

    public func patchLoad(tile: String, icao: String) async throws -> O4PatchLoad {
        try await request("patch_load", ["tile": tile, "icao": icao])
    }

    /// Nodes and ways are written in the order given; tags unchanged.
    public func patchSave(tile: String, icao: String, basePath: String,
                          nodes: [O4PatchNodeRow], ways: [O4PatchWayRow]) async throws -> O4PatchSaveReply {
        try await request("patch_save", [
            "tile": tile, "icao": icao, "base_path": basePath,
            "nodes": nodes.map(\.wireArray), "ways": ways.map(\.wireObject),
        ])
    }

    public func patchRevert(tile: String, icao: String) async throws -> O4PatchRevertReply {
        try await request("patch_revert", ["tile": tile, "icao": icao])
    }

    public func packOutlines(tile: String, icao: String) async throws -> O4PackOutlines {
        try await request("pack_outlines", ["tile": tile, "icao": icao])
    }

    /// `buildDir`: the tile's build folder as the scan reported it
    /// (`O4TileInfo.buildDir`; spec §2 amendment (b)) — where the built DEM
    /// is looked for; nil = the engine's default `Tiles/` folder.
    public func terrainSample(tile: String, icao: String, bbox: O4LatLonBox,
                              spacingM: Double, buildDir: String? = nil) async throws -> O4TerrainSample {
        var arguments: [String: Any] = [
            "tile": tile, "icao": icao, "bbox": bbox.wireArray, "spacing_m": spacingM,
        ]
        if let buildDir, !buildDir.isEmpty { arguments["build_dir"] = buildDir }
        return try await request("terrain_sample", arguments)
    }

    /// The elevation under the map cursor (protocol 1.14, #1308).
    public func cursorElevation(lat: Double, lon: Double, buildDir: String? = nil) async throws -> O4CursorElevation {
        var arguments: [String: Any] = ["lat": lat, "lon": lon]
        if let buildDir, !buildDir.isEmpty { arguments["build_dir"] = buildDir }
        return try await request("cursor_elevation", arguments)
    }

    /// The terrain view's picture over `bbox` (protocol 1.15, #1320):
    /// hillshade plus contours, `pixelWidth` × `pixelHeight` (at most 1024
    /// each); `contourM` nil = the engine's default for the pixel size.
    /// Ask again while the reply is `pending`.
    public func terrainRelief(tile: String, bbox: O4LatLonBox, pixelWidth: Int, pixelHeight: Int,
                              contourM: Double? = nil, buildDir: String? = nil) async throws -> O4TerrainRelief {
        var arguments: [String: Any] = [
            "tile": tile, "bbox": bbox.wireArray, "px_w": pixelWidth, "px_h": pixelHeight,
        ]
        if let contourM { arguments["contour_m"] = contourM }
        if let buildDir, !buildDir.isEmpty { arguments["build_dir"] = buildDir }
        return try await request("terrain_relief", arguments)
    }

    /// The last build's mesh around `bbox` ("Last build"); `buildDir` as
    /// for `terrainSample`.
    public func meshCrop(tile: String, bbox: O4LatLonBox, buildDir: String? = nil) async throws -> O4MeshCrop {
        var arguments: [String: Any] = ["tile": tile, "bbox": bbox.wireArray]
        if let buildDir, !buildDir.isEmpty { arguments["build_dir"] = buildDir }
        return try await request("mesh_crop", arguments)
    }

    /// Asynchronous on the engine side (spec §5): the reply is
    /// `{"status": "started"}` and the `PackObjectsReady` event naming this
    /// command's id carries the result or the error.
    /// `footprintsOnly` (#797): each model's plan hull instead of its
    /// massing — the 2-D map's answer (OTHH: 47 MB in full).
    public func packObjects(tile: String, icao: String, bbox: O4LatLonBox,
                            footprintsOnly: Bool = false) async throws -> O4PackObjects {
        let once = O4ResumeOnce<O4PackObjects>()
        let base: [String: Any] = ["tile": tile, "icao": icao, "bbox": bbox.wireArray]
        let arguments = footprintsOnly ? base.merging(["footprints_only": true]) { a, _ in a } : base
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: "pack_objects",
                 arguments: arguments,
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused pack_objects.")))
                     }
                 },
                 completionEvent: { event in once.resume(Self.decodePackObjectsReady(event)) })
        }
    }

    /// One `PackObjectsReady` event → the typed result or its error.
    static func decodePackObjectsReady(_ event: O4JSON?) -> Result<O4PackObjects, Error> {
        guard let event else { return .failure(O4CommandError("The engine exited before the buildings were read.")) }
        if case .string(let text)? = event["error"], !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        guard let result = event["result"], result != .null else {
            return .failure(O4CommandError("The engine sent no buildings."))
        }
        return Result { try result.decode(O4PackObjects.self) }
    }

    private func request<T: Decodable & Sendable>(_ command: String,
                                                  _ arguments: [String: Any]) async throws -> T {
        try await withCheckedThrowingContinuation { continuation in
            send(command: command, arguments: arguments) { reply in
                continuation.resume(with: Self.decodeReply(reply, command: command))
            }
        }
    }

    /// One reply → the typed result or the engine's error sentence.
    static func decodeReply<T: Decodable>(_ reply: O4Reply, command: String) -> Result<T, Error> {
        guard reply.ok else {
            return .failure(O4CommandError(reply.error ?? "The engine refused \(command)."))
        }
        guard let result = reply.result else {
            return .failure(O4CommandError("The engine sent no result for \(command)."))
        }
        do { return .success(try result.decode(T.self)) } catch {
            return .failure(error as? O4CommandError
                ?? O4CommandError("The engine's \(command) reply could not be read: \(error)"))
        }
    }
}
