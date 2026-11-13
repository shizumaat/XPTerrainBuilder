import SwiftUI
import SceneryKit

/// Settings ▸ Storage ▸ Storage tiers (RULINGS 2026-11-12g): each mounted
/// drive other than the app's own, with the size it may hold of sharp
/// imagery (0: not used). Sharp imagery the disk budget makes low res
/// again moves there and comes back while the drive is connected; without
/// it the imagery is downloaded again. The Qt window's
/// `O4_Qt_Storage_Tiers.TiersBox` is the same.
struct StorageTiersSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @State private var tiers: [O4StorageTier] = []
    @State private var fields: [String: String] = [:]
    @State private var status = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(O4StorageText.tiersTitle).bold()
            Text(O4StorageText.tiersHelp)
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if tiers.isEmpty {
                Text(O4StorageText.tiersNone).foregroundStyle(.secondary)
            }
            ForEach(tiers) { tier in
                HStack {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(tier.name)
                        Text(detail(tier))
                            .scaledFont(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    TextField("GB", text: binding(tier))
                        .frame(width: 70)
                        .multilineTextAlignment(.trailing)
                        .onSubmit { apply(tier) }
                    Text("GB").foregroundStyle(.secondary)
                }
            }
            if !status.isEmpty {
                Text(status).scaledFont(.caption).foregroundStyle(.secondary)
            }
        }
        .task { await refresh() }
    }

    private func detail(_ tier: O4StorageTier) -> String {
        guard tier.mounted else { return O4StorageText.tiersAbsent }
        return O4StorageText.tiersUsed
            .replacingOccurrences(of: "{used}", with: Library.size(tier.usedBytes))
            .replacingOccurrences(of: "{free}", with: Library.size(tier.freeBytes))
    }

    private func binding(_ tier: O4StorageTier) -> Binding<String> {
        Binding(get: { fields[tier.mount] ?? Self.text(tier.sizeGb) },
                set: { fields[tier.mount] = $0 })
    }

    private static func text(_ gigabytes: Double) -> String {
        gigabytes == gigabytes.rounded() ? String(Int(gigabytes)) : String(gigabytes)
    }

    private func refresh() async {
        guard buildModel.engineCapabilities.supports(O4EngineCapabilities.storageTiers),
              let client = buildModel.libraryContext()?.client,
              let answer = try? await client.storageTiers() else { return }
        tiers = answer.volumes
        fields = [:]
    }

    private func apply(_ tier: O4StorageTier) {
        let text = (fields[tier.mount] ?? "").trimmingCharacters(in: .whitespaces)
        guard let gigabytes = Double(text.isEmpty ? "0" : text), gigabytes >= 0,
              let client = buildModel.libraryContext()?.client else {
            status = "A size is 0 or more GB."
            return
        }
        Task {
            do {
                tiers = try await client.storageTierSet(mount: tier.mount, sizeGb: gigabytes).volumes
                fields = [:]
                status = ""
            } catch {
                status = "\(error)"
            }
        }
    }
}
