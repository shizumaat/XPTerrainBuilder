import Foundation

/// A dynamically-typed Ortho4XP config value. The engine's schema declares
/// each variable as int/float/bool/str/list; values cross three boundaries —
/// the schema JSON dump, the key=value cfg files (python literals), and the
/// driver job JSON — so one enum covers parsing and rendering for all three.
public enum O4Value: Sendable, Equatable, Codable {
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case list([O4Value])

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let b = try? container.decode(Bool.self) { self = .bool(b) }
        else if let i = try? container.decode(Int.self) { self = .int(i) }
        else if let d = try? container.decode(Double.self) { self = .double(d) }
        else if let s = try? container.decode(String.self) { self = .string(s) }
        else if let l = try? container.decode([O4Value].self) { self = .list(l) }
        else if container.decodeNil() { self = .string("") }
        else {
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "Unsupported O4Value")
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .bool(let b): try container.encode(b)
        case .int(let i): try container.encode(i)
        case .double(let d): try container.encode(d)
        case .string(let s): try container.encode(s)
        case .list(let l): try container.encode(l)
        }
    }

    /// Rendering for cfg files, matching what the engine writes with str():
    /// True/False for bools, python list repr for lists, bare text otherwise.
    public var cfgLiteral: String {
        switch self {
        case .bool(let b): return b ? "True" : "False"
        case .int(let i): return String(i)
        case .double(let d):
            return d == d.rounded() && abs(d) < 1e15
                ? String(format: "%.1f", d) : String(d)
        case .string(let s): return s
        case .list(let items):
            return "[" + items.map { $0.listElementLiteral }.joined(separator: ", ") + "]"
        }
    }

    /// Inside a list, strings need python quotes.
    private var listElementLiteral: String {
        if case .string(let s) = self {
            return "'" + s.replacingOccurrences(of: "'", with: "\\'") + "'"
        }
        return cfgLiteral
    }

    /// Parse a cfg-file value string according to the schema-declared type
    /// ("int" / "float" / "bool" / "str" / "list").
    public static func parse(_ raw: String, typeName: String) -> O4Value? {
        let value = raw.trimmingCharacters(in: .whitespaces)
        switch typeName {
        case "bool":
            if value == "True" { return .bool(true) }
            if value == "False" { return .bool(false) }
            return nil
        case "int":
            return Int(value).map { .int($0) }
        case "float":
            return Double(value).map { .double($0) }
        case "list":
            var scanner = PythonLiteralScanner(value)
            return scanner.parseValue()
        default:
            // Legacy configs quoted strings; the engine strips those too.
            var s = value
            if s.count >= 2, (s.hasPrefix("\"") && s.hasSuffix("\"")) || (s.hasPrefix("'") && s.hasSuffix("'")) {
                s = String(s.dropFirst().dropLast())
            }
            return .string(s)
        }
    }

    public var stringValue: String? { if case .string(let s) = self { return s }; return nil }
    public var boolValue: Bool? { if case .bool(let b) = self { return b }; return nil }
    public var intValue: Int? { if case .int(let i) = self { return i }; return nil }
}

/// Minimal python-literal parser covering what appears in cfg files: numbers,
/// quoted strings, booleans, and (nested) lists — e.g. masks_width=100,
/// zone_list=[[[47.1, 11.2, ...], 18, 'BI']].
struct PythonLiteralScanner {
    private let chars: [Character]
    private var index = 0

    init(_ text: String) {
        chars = Array(text)
    }

    mutating func parseValue() -> O4Value? {
        skipSpaces()
        guard index < chars.count else { return nil }
        switch chars[index] {
        case "[":
            index += 1
            var items: [O4Value] = []
            while true {
                skipSpaces()
                guard index < chars.count else { return nil }
                if chars[index] == "]" { index += 1; break }
                guard let item = parseValue() else { return nil }
                items.append(item)
                skipSpaces()
                if index < chars.count, chars[index] == "," { index += 1 }
            }
            return .list(items)
        case "'", "\"":
            let quote = chars[index]
            index += 1
            var s = ""
            while index < chars.count, chars[index] != quote {
                if chars[index] == "\\", index + 1 < chars.count { index += 1 }
                s.append(chars[index])
                index += 1
            }
            guard index < chars.count else { return nil }
            index += 1
            return .string(s)
        default:
            var token = ""
            while index < chars.count, !",]) ".contains(chars[index]) {
                token.append(chars[index])
                index += 1
            }
            if token == "True" { return .bool(true) }
            if token == "False" { return .bool(false) }
            if let i = Int(token) { return .int(i) }
            if let d = Double(token) { return .double(d) }
            return token.isEmpty ? nil : .string(token)
        }
    }

    private mutating func skipSpaces() {
        while index < chars.count, chars[index] == " " { index += 1 }
    }
}

// MARK: - Schema

/// The engine's config schema, as dumped by o4_schema_dump.py from
/// O4_Cfg_Vars — names, types, defaults, hints, allowed values, and the
/// ordered GUI groups. Extracted from whatever engine is installed, so a
/// newer engine's added options appear without an app update; the bundled
/// snapshot covers first launch and engines without a working python.
public struct OrthoConfigSchema: Sendable, Codable, Equatable {
    public struct Variable: Sendable, Codable, Equatable {
        public let name: String
        /// "int" / "float" / "bool" / "str" / "list"
        public let type: String
        public let `default`: O4Value
        public let hint: String
        public let values: [String]?
        /// Human titles for `values` entries (dev engines ship these).
        public let valueLabels: [String: String]?
        public let module: String?
        public let shortName: String?

        /// GUI label ("high_zl_airports" over "cover_airports_with_highres").
        public var label: String { shortName ?? name }

        public func label(forValue value: String) -> String {
            valueLabels?[value] ?? value
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            name = try c.decode(String.self, forKey: .name)
            type = try c.decode(String.self, forKey: .type)
            hint = try c.decodeIfPresent(String.self, forKey: .hint) ?? ""
            values = try c.decodeIfPresent([String].self, forKey: .values)
            valueLabels = try c.decodeIfPresent([String: String].self, forKey: .valueLabels)
            module = try c.decodeIfPresent(String.self, forKey: .module)
            shortName = try c.decodeIfPresent(String.self, forKey: .shortName)
            let raw = try c.decodeIfPresent(O4Value.self, forKey: .default) ?? .string("")
            // JSON "2.0" decodes as Int; a float-typed variable's default
            // must stay a float or it renders as "2" and equality breaks.
            if type == "float", case .int(let i) = raw {
                `default` = .double(Double(i))
            } else {
                `default` = raw
            }
        }
    }

    public let engineVersion: String
    /// Group key ("app", "vector", "mesh", "mask", "dsf", "other") to the
    /// ordered variable names of that group.
    public let groups: [String: [String]]
    public let vars: [String: Variable]

    public init(engineVersion: String, groups: [String: [String]], vars: [String: Variable]) {
        self.engineVersion = engineVersion
        self.groups = groups
        self.vars = vars
    }

    /// Display order and titles for the grouped settings UI.
    public static let groupOrder: [(key: String, title: String)] = [
        ("app", "Application"),
        ("vector", "Vector"),
        ("mesh", "Mesh"),
        ("mask", "Water Masks"),
        ("dsf", "DSF / Imagery"),
        ("other", "Elevation"),
    ]

    public func variables(inGroup key: String) -> [Variable] {
        (groups[key] ?? []).compactMap { vars[$0] }
    }

    public static func decode(from data: Data) throws -> OrthoConfigSchema {
        try JSONDecoder().decode(OrthoConfigSchema.self, from: data)
    }

    /// The schema snapshot bundled with the app (generated from the engine
    /// version the app was developed against).
    public static func bundledSnapshot() -> OrthoConfigSchema? {
        guard let url = Bundle.module.url(forResource: "o4_schema_snapshot", withExtension: "json"),
              let data = try? Data(contentsOf: url)
        else { return nil }
        return try? decode(from: data)
    }
}

// MARK: - Config files

/// Reads and writes the engine's key=value config files (Ortho4XP.cfg and
/// the per-tile Ortho4XP_±xx±yyy.cfg). Writes preserve unknown keys and line
/// order — a newer engine's options survive an older app editing the file —
/// and keep the engine's own .bak convention.
public struct OrthoConfigFile: Sendable {
    public private(set) var lines: [String]

    public init(lines: [String] = []) {
        self.lines = lines
    }

    public init(contentsOf url: URL) throws {
        let text = try String(contentsOf: url, encoding: .utf8)
        lines = text.components(separatedBy: .newlines)
        if lines.last == "" { lines.removeLast() }
    }

    /// Raw string values by key (last occurrence wins, like the engine's
    /// line-by-line exec).
    public var rawValues: [String: String] {
        var out: [String: String] = [:]
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty, !trimmed.hasPrefix("#"),
                  let eq = trimmed.firstIndex(of: "=") else { continue }
            let key = String(trimmed[..<eq]).trimmingCharacters(in: .whitespaces)
            out[key] = String(trimmed[trimmed.index(after: eq)...])
        }
        return out
    }

    /// Typed values for every schema variable present in the file.
    public func values(schema: OrthoConfigSchema) -> [String: O4Value] {
        var out: [String: O4Value] = [:]
        for (key, raw) in rawValues {
            guard let variable = schema.vars[key] ?? schema.vars["global_" + key] else { continue }
            if let value = O4Value.parse(raw, typeName: variable.type) {
                out[key] = value
            }
        }
        return out
    }

    /// Sets (or appends) a value, preserving all other content.
    public mutating func set(_ key: String, to value: O4Value) {
        let rendered = "\(key)=\(value.cfgLiteral)"
        for (i, line) in lines.enumerated() {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.hasPrefix("#"), let eq = trimmed.firstIndex(of: "=") else { continue }
            if String(trimmed[..<eq]).trimmingCharacters(in: .whitespaces) == key {
                lines[i] = rendered
                return
            }
        }
        lines.append(rendered)
    }

    /// Removes a key entirely (used to revert a per-tile override back to
    /// the inherited global value). Comments and other keys survive.
    public mutating func remove(_ key: String) {
        lines.removeAll { line in
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.hasPrefix("#"), let eq = trimmed.firstIndex(of: "=") else { return false }
            return String(trimmed[..<eq]).trimmingCharacters(in: .whitespaces) == key
        }
    }

    public func write(to url: URL) throws {
        let backup = url.appendingPathExtension("bak")
        let fm = FileManager.default
        if fm.fileExists(atPath: url.path) {
            try? fm.removeItem(at: backup)
            try? fm.copyItem(at: url, to: backup)
        }
        let text = lines.joined(separator: "\n") + "\n"
        try text.write(to: url, atomically: true, encoding: .utf8)
    }
}
