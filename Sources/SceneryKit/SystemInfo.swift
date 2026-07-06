import Foundation
import Metal

/// The hardware this Mac actually has, so performance warnings compare
/// against reality instead of a hard-coded budget.
public struct SystemInfo: Codable, Sendable {
    public let chipName: String
    public let ramBytes: Int64
    /// Metal's recommended working-set size — the practical VRAM budget.
    /// On Apple Silicon (unified memory) this is ~70-75% of RAM.
    public let vramBudgetBytes: Int64

    public static func current() -> SystemInfo {
        var chip = "Unknown"
        var size = 0
        if sysctlbyname("machdep.cpu.brand_string", nil, &size, nil, 0) == 0, size > 0 {
            var buffer = [CChar](repeating: 0, count: size)
            if sysctlbyname("machdep.cpu.brand_string", &buffer, &size, nil, 0) == 0 {
                chip = String(cString: buffer)
            }
        }
        let ram = Int64(ProcessInfo.processInfo.physicalMemory)
        let vram = MTLCreateSystemDefaultDevice()
            .map { Int64($0.recommendedMaxWorkingSetSize) } ?? ram / 2
        return SystemInfo(chipName: chip, ramBytes: ram, vramBudgetBytes: vram)
    }

    public var summary: String {
        let ramText = ByteCountFormatter.string(fromByteCount: ramBytes, countStyle: .memory)
        let vramText = ByteCountFormatter.string(fromByteCount: vramBudgetBytes, countStyle: .memory)
        return "\(chipName) · \(ramText) RAM · ~\(vramText) usable VRAM"
    }
}
