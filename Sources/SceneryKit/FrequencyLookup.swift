import Foundation

/// A real-world ATC frequency for an airport, from a public source.
public struct LookedUpFrequency: Sendable {
    /// apt.dat row-code suffix this frequency belongs to:
    /// "2" clearance, "3" ground, "4" tower, "5" approach, "6" departure.
    public let codeSuffix: Character
    /// Frequency in kHz (e.g. 132030 = 132.030 MHz).
    public let khz: Int
    public let label: String
    public let source: String

    public init(codeSuffix: Character, khz: Int, label: String, source: String) {
        self.codeSuffix = codeSuffix
        self.khz = khz
        self.label = label
        self.source = source
    }
}

/// Fetches published ATC frequencies for an airport: AirNav for US
/// identifiers (rich, per-controller, includes sectors), OurAirports
/// elsewhere (worldwide, community-maintained). Only used from the FIX
/// path — analysis stays offline.
public enum FrequencyLookup {
    static let vhfBandKhz = 118_000...136_990

    /// Blocking fetch with a bounded timeout; [] on any failure — the fix
    /// falls back to assigning an unused in-band channel.
    public static func fetch(icao: String) -> [LookedUpFrequency] {
        let sanitized = icao.filter { $0.isLetter || $0.isNumber }
        guard !sanitized.isEmpty else { return [] }
        let isUS = sanitized.first == "K" || sanitized.first == "P"
            || (sanitized.count == 3 && sanitized.allSatisfy { $0.isNumber || $0.isUppercase })
        let candidates = isUS
            ? ["https://www.airnav.com/airport/\(sanitized)",
               "https://ourairports.com/airports/\(sanitized)/frequencies.html"]
            : ["https://ourairports.com/airports/\(sanitized)/frequencies.html"]
        for urlString in candidates {
            guard let url = URL(string: urlString), let html = download(url) else { continue }
            let parsed = urlString.contains("airnav")
                ? parseAirNav(html: html)
                : parseOurAirports(html: html)
            if !parsed.isEmpty { return parsed }
        }
        return []
    }

    static func download(_ url: URL) -> String? {
        var request = URLRequest(url: url, timeoutInterval: 10)
        request.setValue("Mozilla/5.0 (Macintosh) XPTerrainBuilder", forHTTPHeaderField: "User-Agent")
        let semaphore = DispatchSemaphore(value: 0)
        var result: String?
        URLSession.shared.dataTask(with: request) { data, response, _ in
            if let data, (response as? HTTPURLResponse)?.statusCode == 200 {
                result = String(data: data, encoding: .utf8)
                    ?? String(data: data, encoding: .isoLatin1)
            }
            semaphore.signal()
        }.resume()
        _ = semaphore.wait(timeout: .now() + 15)
        return result
    }

    // MARK: - AirNav (US)

    /// "Airport Communications" table rows:
    /// `<TR><TD ...>NASHVILLE APPROACH:&nbsp;</TD><TD ...>118.4 ;030-196 119.35 ;197-029 360.7 ...</TD></TR>`
    static func parseAirNav(html: String) -> [LookedUpFrequency] {
        guard let regex = try? NSRegularExpression(
            pattern: #"<TR><TD[^>]*>([^<:]+):&nbsp;</TD><TD[^>]*>([^<]+)</TD></TR>"#,
            options: [.caseInsensitive]) else { return [] }
        var results: [LookedUpFrequency] = []
        let range = NSRange(html.startIndex..., in: html)
        regex.enumerateMatches(in: html, options: [], range: range) { match, _, _ in
            guard let match,
                  let name = html.substring(match: match, group: 1)?
                    .trimmingCharacters(in: .whitespaces),
                  let values = html.substring(match: match, group: 2)
            else { return }
            guard let suffix = codeSuffix(forName: name) else { return }
            for khz in frequenciesKhz(in: values) where vhfBandKhz.contains(khz) {
                results.append(LookedUpFrequency(codeSuffix: suffix, khz: khz,
                                                 label: name, source: "AirNav"))
            }
        }
        return results
    }

    // MARK: - OurAirports (worldwide)

    /// Sections like:
    /// `<section class="frequency listing row"> ... <b>ARR</b> ... 132.03 MHz ... Leeuwarden Arrival`
    static func parseOurAirports(html: String) -> [LookedUpFrequency] {
        var results: [LookedUpFrequency] = []
        let sections = html.components(separatedBy: "class=\"frequency listing row\"").dropFirst()
        guard let typeRegex = try? NSRegularExpression(pattern: #"<b>([A-Z/ &;]+)</b>"#),
              let freqRegex = try? NSRegularExpression(pattern: #"([\d]{2,3}\.[\d]{1,3})\s*MHz"#)
        else { return [] }
        for section in sections {
            let text = String(section.prefix(800))
            let range = NSRange(text.startIndex..., in: text)
            guard let typeMatch = typeRegex.firstMatch(in: text, options: [], range: range),
                  let type = text.substring(match: typeMatch, group: 1),
                  let suffix = codeSuffix(forName: type),
                  let freqMatch = freqRegex.firstMatch(in: text, options: [], range: range),
                  let mhzString = text.substring(match: freqMatch, group: 1),
                  let mhz = Double(mhzString)
            else { continue }
            let khz = Int((mhz * 1000).rounded())
            guard vhfBandKhz.contains(khz) else { continue }
            results.append(LookedUpFrequency(codeSuffix: suffix, khz: khz,
                                             label: type, source: "OurAirports"))
        }
        return results
    }

    // MARK: - Shared

    /// Facility keywords -> apt.dat row-code suffix. Names that are routes,
    /// weather or emergency channels return nil.
    static func codeSuffix(forName name: String) -> Character? {
        let upper = name.uppercased()
        if upper.contains("GROUND") || upper == "GND" { return "3" }
        if upper.contains("TOWER") || upper == "TWR" { return "4" }
        if upper.contains("APPROACH") || upper.contains("ARRIVAL")
            || upper == "APP" || upper == "ARR" || upper == "A/D" { return "5" }
        if upper.contains("DEPARTURE") || upper == "DEP" { return "6" }
        if upper.contains("CLEARANCE") || upper == "DEL" || upper == "CLD" || upper == "CLNC" { return "2" }
        return nil
    }

    /// Every "118.4"-style number in an AirNav value cell (sector notes like
    /// ";030-196" and phone numbers are shaped differently and don't match).
    static func frequenciesKhz(in values: String) -> [Int] {
        guard let regex = try? NSRegularExpression(pattern: #"(?<![\d-])(\d{2,3}\.\d{1,3})"#) else { return [] }
        let range = NSRange(values.startIndex..., in: values)
        return regex.matches(in: values, options: [], range: range).compactMap { match in
            values.substring(match: match, group: 1)
                .flatMap(Double.init)
                .map { Int(($0 * 1000).rounded()) }
        }
    }
}
