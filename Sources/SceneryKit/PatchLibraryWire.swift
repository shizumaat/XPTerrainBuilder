import Foundation

// MARK: - Patch library (#1699 phase 2)

/// The shared patch library's airport entries (`Ortho4XP/src/patch_library`,
/// commands in `o4_engine.library.PATCH_LIBRARY_COMMANDS`). Every command
/// replies `{"status": "started"}` and completes with `LibraryReady`, like
/// the other Library commands. Reading the library needs no account;
/// publishing signs in to GitHub with the device flow.
extension O4ProtocolVersion {
    /// The patch library commands (protocol 1.24).
    public static func supportsPatchLibrary(_ version: String) -> Bool {
        isAtLeast(version, 1, 24)
    }
}

/// One airport the check when the app opens lists (`scan.check`): an
/// entry the user has not used (`available`), a newer version of the one
/// used (`newer`), a pack that changed under a used patch (`pack_changed`),
/// or entries only for another version of the pack (`other`).
public struct O4PatchLibraryRow: Decodable, Equatable, Sendable, Identifiable {
    public let icao: String
    public let tile: String
    public let state: String
    public let pack: String
    public let entryPack: String
    public let version: Int
    public let localVersion: Int?
    public let entry: String
    public let signature: String
    public let verified: Bool
    public let publisher: String
    public let solvedUsable: Bool
    public let reason: String
    public let warning: String

    public var id: String { icao + "|" + entry }

    private enum CodingKeys: String, CodingKey {
        case icao, tile, state, pack, version, entry, signature, verified, publisher
        case reason, warning
        case entryPack = "entry_pack", localVersion = "local_version"
        case solvedUsable = "solved_usable"
    }
}

/// `library_check`: `configured` false until the library is set up.
public struct O4PatchLibraryCheck: Decodable, Equatable, Sendable {
    public let configured: Bool
    public let rows: [O4PatchLibraryRow]
    public let checked: String
}

/// `library_apply`: `mode` is `solved` (the next build skips the airport's
/// solve) or `re-solve` (the reason says why; the airport is solved here).
public struct O4PatchLibraryApplied: Decodable, Equatable, Sendable {
    public let icao: String
    public let tile: String
    public let version: Int
    public let mode: String
    public let reason: String
    public let edits: String
    public let conflict: String?
    public let files: Int
    public let warning: String
}

/// One library entry for an airport the build grades, by match tier
/// (`exact`, `same_pack`, `other_pack`), best first.
public struct O4PatchLibraryMatch: Decodable, Equatable, Sendable, Identifiable {
    public let tier: String
    public let entry: String
    public let pack: String
    public let version: Int
    public let verified: Bool
    public let publisher: String
    public let solvedUsable: Bool
    public let reason: String

    public var id: String { entry }

    private enum CodingKeys: String, CodingKey {
        case tier, entry, pack, version, verified, publisher, reason
        case solvedUsable = "solved_usable"
    }
}

/// `library_matches`: per graded airport, its library entries.
public struct O4PatchLibraryMatches: Decodable, Equatable, Sendable {
    public let configured: Bool
    public let airports: [String: [O4PatchLibraryMatch]]
}

/// `library_publish_preview`: what "Publish Patch" would publish.
public struct O4PatchLibraryPreview: Decodable, Equatable, Sendable {
    public struct File: Decodable, Equatable, Sendable {
        public let name: String
        public let bytes: Int64
    }
    public let icao: String
    public let entry: String
    public let version: Int
    public let pack: String
    public let kind: String
    public let files: [File]
    public let bytes: Int64
    public let problems: [String]
    public let verified: Bool
    public let signedIn: String
    public let licence: String
    public let licenceAccepted: Bool
    public let attribution: String

    private enum CodingKeys: String, CodingKey {
        case icao, entry, version, pack, kind, files, bytes, problems, verified
        case licence, attribution
        case signedIn = "signed_in", licenceAccepted = "licence_accepted"
    }
}

/// `library_signin_start`: the code to enter at `verificationUri`.
public struct O4PatchLibrarySignIn: Decodable, Equatable, Sendable {
    public let userCode: String
    public let verificationUri: String
    public let deviceCode: String
    public let interval: Int?

    private enum CodingKeys: String, CodingKey {
        case interval
        case userCode = "user_code", verificationUri = "verification_uri"
        case deviceCode = "device_code"
    }
}

/// `library_signin_poll`: `ok` (signed in as `login`), `pending`,
/// `slow_down`, `expired` or `denied`.
public struct O4PatchLibrarySignInPoll: Decodable, Equatable, Sendable {
    public let status: String
    public let login: String
}

/// `library_publish`: the pull request opened on the library.
public struct O4PatchLibraryPublished: Decodable, Equatable, Sendable {
    public let pullUrl: String
    public let entry: String
    public let version: Int
    public let autoMerge: Bool

    private enum CodingKeys: String, CodingKey {
        case entry, version
        case pullUrl = "pull_url", autoMerge = "auto_merge"
    }
}

/// `library_ignore` / `library_signout`: nothing the app reads.
public struct O4PatchLibraryDone: Decodable, Equatable, Sendable {}

extension OrthoEngineClient {
    public func libraryCheck(workingDir: String, force: Bool) async throws -> O4PatchLibraryCheck {
        try await libraryRequest("library_check", ["working_dir": workingDir, "force": force])
    }

    public func libraryMatches(tiles: [O4TileRef], workingDir: String) async throws -> O4PatchLibraryMatches {
        try await libraryRequest("library_matches", [
            "cells": tiles.map { [$0.lat, $0.lon] }, "working_dir": workingDir,
        ])
    }

    /// Downloads and lays down one entry; nothing is applied without the
    /// user's press (Build / Update / Use).
    public func libraryApply(entry: String, workingDir: String) async throws -> O4PatchLibraryApplied {
        try await libraryRequest("library_apply", ["entry": entry, "working_dir": workingDir])
    }

    public func libraryIgnore(icao: String, signature: String, version: Int) async throws {
        let _: O4PatchLibraryDone = try await libraryRequest(
            "library_ignore", ["icao": icao, "signature": signature, "version": version])
    }

    public func libraryPublishPreview(lat: Int, lon: Int, icao: String, workingDir: String,
                                      kind: String) async throws -> O4PatchLibraryPreview {
        try await libraryRequest("library_publish_preview", [
            "lat": lat, "lon": lon, "icao": icao, "working_dir": workingDir, "kind": kind,
        ])
    }

    public func librarySignInStart() async throws -> O4PatchLibrarySignIn {
        try await libraryRequest("library_signin_start", [:])
    }

    public func librarySignInPoll(deviceCode: String) async throws -> O4PatchLibrarySignInPoll {
        try await libraryRequest("library_signin_poll", ["device_code": deviceCode])
    }

    public func librarySignOut() async throws {
        let _: O4PatchLibraryDone = try await libraryRequest("library_signout", [:])
    }

    public func libraryPublish(lat: Int, lon: Int, icao: String, workingDir: String, kind: String,
                               notes: String, accept: Bool) async throws -> O4PatchLibraryPublished {
        try await libraryRequest("library_publish", [
            "lat": lat, "lon": lon, "icao": icao, "working_dir": workingDir, "kind": kind,
            "notes": notes, "accept": accept,
        ])
    }
}
