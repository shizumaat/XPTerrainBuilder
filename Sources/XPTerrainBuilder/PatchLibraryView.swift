import AppKit
import SwiftUI
import SceneryKit

/// The shared patch library in the Mac app (#1699 phase 2). Three homes,
/// each mirrored in the Qt window (`O4_Qt_Patch_Library.py`):
/// - Library window ▸ "Patch library": the check when the app opens, one
///   row per airport with Build / Update / Ignore (`PatchLibrarySection`);
/// - Library window ▸ "Publish Patch…": preview, licence, GitHub sign-in,
///   pull request (`PublishPatchSheet`);
/// - Build box ▸ Airports card ▸ "Library patches": the match list for the
///   airports this build grades (`LibraryMatchList`).
enum PatchLibraryText {
    static let title = "Patch library"
    static let licence = "I publish this patch under the Open Database License (ODbL) 1.0 "
        + "and each source's terms shown above."
    static let noncommercial = "Non-commercial: a source allows non-commercial use only, "
        + "so the whole entry is marked non-commercial."

    /// The preview's lines for each source's terms (owner Q319), as the Qt
    /// window's `terms_lines` writes them.
    static func terms(_ preview: O4PatchLibraryPreview) -> [String] {
        let lines = (preview.sources ?? []).map { source in
            "Source: \(source.provider) — \(source.licence)"
                + (source.noncommercial ? " · non-commercial" : "")
        }
        return lines + ((preview.noncommercial ?? false) ? [noncommercial] : [])
    }

    static func state(_ row: O4PatchLibraryRow) -> String {
        switch row.state {
        case "available": return "patch v\(row.version) available"
        case "newer": return "v\(row.version) available (you have v\(row.localVersion ?? 0))"
        case "pack_changed": return "your pack changed — the next build solves it here"
        default: return "patches for another version of this pack"
        }
    }

    static func tier(_ match: O4PatchLibraryMatch) -> String {
        switch match.tier {
        case "exact": return "exact match"
        case "same_pack": return "same pack, other version"
        default: return "other pack"
        }
    }
}

struct PatchLibrarySection: View {
    @EnvironmentObject private var buildModel: BuildModel
    @State private var status = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(PatchLibraryText.title).bold()
                Spacer()
                Text(status.isEmpty ? buildModel.patchLibraryStatus : status)
                    .foregroundStyle(.secondary).lineLimit(2)
                Button("Check Now") { buildModel.checkPatchLibrary(force: true) }
                    .help("Read the library's index again")
                    .disabled(buildModel.patchLibraryClient() == nil)
            }
            let rows = buildModel.patchLibraryCheck?.rows ?? []
            if rows.isEmpty {
                Text(buildModel.patchLibraryCheck == nil
                     ? "Not checked yet."
                     : "No patch in the library for your installed airports and built tiles.")
                    .foregroundStyle(.secondary)
            }
            ForEach(rows) { row in
                HStack(spacing: 8) {
                    Text(row.icao).bold().monospaced()
                    Text(row.entryPack).lineLimit(1).truncationMode(.middle)
                    if row.verified {
                        Label("Verified developer", systemImage: "checkmark.seal")
                            .labelStyle(.iconOnly).help("Published by the pack's own developer")
                    }
                    Text(PatchLibraryText.state(row)).foregroundStyle(.secondary)
                    if !row.solvedUsable, !row.reason.isEmpty, row.state != "pack_changed" {
                        Text("(\(row.reason))").foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer()
                    if row.state == "available" || row.state == "other" {
                        Button(row.state == "other" ? "Use" : "Build") { apply(row) }
                    } else if row.state == "newer" {
                        Button("Update") { apply(row) }
                    }
                    Button("Ignore") { Task { await buildModel.ignorePatchLibraryRow(row) } }
                }
                .disabled(buildModel.isBuilding)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func apply(_ row: O4PatchLibraryRow) {
        status = "Downloading \(row.icao)…"
        Task { status = await buildModel.applyPatchLibraryEntry(row.entry) }
    }
}

/// Build box ▸ Airports card: the library's entries for the airports this
/// build grades, best match first; "Use" lays one down before the build.
struct LibraryMatchList: View {
    @EnvironmentObject private var buildModel: BuildModel
    let matches: O4PatchLibraryMatches?
    @State private var status = ""

    var body: some View {
        if let matches, !matches.airports.isEmpty {
            VStack(alignment: .leading, spacing: 2) {
                Text("Library patches").scaledFont(.caption, weight: .semibold)
                ForEach(matches.airports.keys.sorted(), id: \.self) { icao in
                    if let best = matches.airports[icao]?.first {
                        HStack(spacing: 6) {
                            Text(icao).scaledFont(.caption, weight: .semibold)
                            Text("v\(best.version) · \(PatchLibraryText.tier(best))"
                                 + (best.verified ? " · verified developer" : ""))
                                .scaledFont(.caption).foregroundStyle(.secondary)
                                .help(best.solvedUsable ? "Skips this airport's solve"
                                      : "Solved here from its edits: \(best.reason)")
                            Spacer(minLength: 4)
                            Button("Use") {
                                Task { status = await buildModel.applyPatchLibraryEntry(best.entry) }
                            }
                            .controlSize(.small)
                            .disabled(buildModel.isBuilding)
                        }
                    }
                }
                if !status.isEmpty {
                    Text(status).scaledFont(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(.leading, 18)
        }
    }
}

/// Library window ▸ Publish Patch…: one airport of the selected built tile.
struct PublishPatchSheet: View {
    @EnvironmentObject private var buildModel: BuildModel
    @Environment(\.dismiss) private var dismiss
    let tile: O4LibraryTile
    @State private var icao = ""
    @State private var kind = "freeware"
    @State private var preview: O4PatchLibraryPreview?
    @State private var accepted = false
    @State private var signIn: O4PatchLibrarySignIn?
    @State private var status = ""
    @State private var busy = false
    @State private var pullURL: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Publish Patch — \(tile.tile)").font(.headline)
            Picker("Airport", selection: $icao) {
                ForEach(tile.airports, id: \.self) { Text($0).tag($0) }
            }
            Picker("Pack", selection: $kind) {
                Text("Free pack").tag("freeware")
                Text("Paid pack").tag("payware")
            }
            .pickerStyle(.segmented)
            .help("The global default airports are recognised by themselves")
            if let preview {
                previewBox(preview)
            }
            Toggle(PatchLibraryText.licence, isOn: $accepted)
            if let signIn {
                HStack {
                    Text("Enter \(signIn.userCode) at").textSelection(.enabled)
                    Link(signIn.verificationUri, destination: URL(string: signIn.verificationUri)
                         ?? URL(string: "https://github.com/login/device")!)
                }
            }
            Text(status).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let pullURL, let url = URL(string: pullURL) {
                Link("Open the pull request", destination: url)
            }
            HStack {
                Button("Preview") { Task { await runPreview() } }.disabled(busy || icao.isEmpty)
                if preview != nil, preview?.signedIn.isEmpty ?? true {
                    Button("Sign In to GitHub…") { Task { await runSignIn() } }.disabled(busy)
                }
                Spacer()
                Button("Close") { dismiss() }
                Button("Publish") { Task { await runPublish() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(busy || !accepted || !(preview?.problems.isEmpty ?? false)
                              || (preview?.signedIn.isEmpty ?? true))
            }
        }
        .padding(16)
        .frame(width: 520)
        .onAppear {
            icao = tile.airports.first ?? ""
        }
    }

    private func previewBox(_ p: O4PatchLibraryPreview) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(p.icao) version \(p.version) for \(p.pack) (\(p.kind)) · \(Library.size(p.bytes))")
            Text(p.verified ? "You are this pack's verified developer: it merges when the checks pass."
                 : "It goes to the community reviewers.")
                .foregroundStyle(.secondary)
            ForEach(PatchLibraryText.terms(p), id: \.self) { Text($0).foregroundStyle(.secondary) }
            ForEach(p.problems, id: \.self) { Text("• " + $0).foregroundStyle(.red) }
        }
        .scaledFont(.caption)
    }

    private func client() -> (OrthoEngineClient, String)? {
        guard let client = buildModel.patchLibraryClient(), let base = buildModel.tileBaseFolder else {
            status = "The engine is not running."
            return nil
        }
        return (client, base.path)
    }

    private func runPreview() async {
        guard let (client, folder) = client() else { return }
        busy = true
        status = "Packaging \(icao)…"
        do {
            preview = try await client.libraryPublishPreview(
                lat: tile.lat, lon: tile.lon, icao: icao, workingDir: folder, kind: kind)
            accepted = accepted || (preview?.licenceAccepted ?? false)
            status = preview?.problems.isEmpty ?? false ? "Ready to publish." : "The library would refuse it."
        } catch {
            status = "\(error)"
        }
        busy = false
    }

    private func runSignIn() async {
        guard let (client, _) = client() else { return }
        busy = true
        do {
            let start = try await client.librarySignInStart()
            signIn = start
            if let url = URL(string: start.verificationUri) { NSWorkspace.shared.open(url) }
            status = "Waiting for GitHub…"
            for _ in 0..<180 {
                try await Task.sleep(nanoseconds: UInt64(max(start.interval ?? 5, 1)) * 1_000_000_000)
                let poll = try await client.librarySignInPoll(deviceCode: start.deviceCode)
                if poll.status == "ok" {
                    status = "Signed in as \(poll.login)."
                    signIn = nil
                    busy = false
                    await runPreview()
                    return
                }
                if poll.status == "expired" || poll.status == "denied" {
                    status = "The sign-in was \(poll.status). Try again."
                    break
                }
            }
        } catch {
            status = "\(error)"
        }
        signIn = nil
        busy = false
    }

    private func runPublish() async {
        guard let (client, folder) = client() else { return }
        busy = true
        status = "Publishing \(icao)…"
        do {
            let done = try await client.libraryPublish(
                lat: tile.lat, lon: tile.lon, icao: icao, workingDir: folder, kind: kind,
                notes: "", accept: accepted)
            pullURL = done.pullUrl
            status = done.autoMerge
                ? "Published v\(done.version): it merges when the library's checks pass."
                : "Published v\(done.version): the community reviewers will look at it."
        } catch {
            status = "\(error)"
        }
        busy = false
    }
}
