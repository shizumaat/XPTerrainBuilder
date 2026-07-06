import Testing
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
@testable import SceneryKit

@Suite struct DDSEncoderTests {

    func writePNG(width: Int, height: Int, alpha: Bool, to url: URL) throws {
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        for y in 0..<height {
            for x in 0..<width {
                let i = (y * width + x) * 4
                pixels[i] = UInt8((x * 255) / max(1, width - 1))
                pixels[i + 1] = UInt8((y * 255) / max(1, height - 1))
                pixels[i + 2] = 128
                pixels[i + 3] = alpha ? UInt8((x * 255) / max(1, width - 1)) : 255
            }
        }
        let context = CGContext(
            data: &pixels, width: width, height: height, bitsPerComponent: 8,
            bytesPerRow: width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        let image = context.makeImage()!
        let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(dest, image, nil)
        #expect(CGImageDestinationFinalize(dest))
    }

    @Test func encodesOpaquePNGAsDXT1WithFullMipChain() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDDS-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let png = dir.appendingPathComponent("tex.png")
        try writePNG(width: 64, height: 32, alpha: false, to: png)

        let dds = try DDSEncoder.encodePNG(at: png).get()
        let ddsURL = dir.appendingPathComponent("tex.dds")
        try dds.write(to: ddsURL)

        let info = try #require(TextureInspector.inspect(url: ddsURL))
        #expect(info.format == .dds)
        #expect(info.width == 64)
        #expect(info.height == 32)
        #expect(info.mipMapCount == 7) // 64x32 ... 1x1
        // FourCC at byte 84.
        #expect(String(decoding: dds[84..<88], as: UTF8.self) == "DXT1")
    }

    @Test func encodesAlphaPNGAsDXT5() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDDS-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let png = dir.appendingPathComponent("tex.png")
        try writePNG(width: 16, height: 16, alpha: true, to: png)

        let dds = try DDSEncoder.encodePNG(at: png).get()
        #expect(String(decoding: dds[84..<88], as: UTF8.self) == "DXT5")
        // 16x16 DXT5 base level = 4x4 blocks * 16 bytes = 256 bytes.
        // header(128) + 256 + mips(4x4:16 + rest: 16*4) > 384
        #expect(dds.count > 128 + 256)
    }

    @Test func conversionFixRoundTrip() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDDSFix-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let png = dir.appendingPathComponent("ground.png")
        try writePNG(width: 32, height: 32, alpha: false, to: png)
        let originalPNG = try Data(contentsOf: png)

        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let finding = Finding(
            checkID: "C-04", severity: .warning, category: .packageHealth,
            title: "t", detail: "d", fixability: .auto,
            proposedFix: .convertPNGToDDS(pngPath: png.path)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")

        let ddsURL = dir.appendingPathComponent("ground.dds")
        #expect(FileManager.default.fileExists(atPath: ddsURL.path))
        #expect(!FileManager.default.fileExists(atPath: png.path), "png should be retired to backup")
        #expect(FileManager.default.fileExists(atPath: png.path + FixEngine.backupSuffix))

        // Revert restores the PNG and removes the DDS.
        let reverts = engine.revert(engine.log.load())
        #expect(reverts.allSatisfy { $0.success })
        #expect(try Data(contentsOf: png) == originalPNG)
        #expect(!FileManager.default.fileExists(atPath: ddsURL.path))
    }
}
