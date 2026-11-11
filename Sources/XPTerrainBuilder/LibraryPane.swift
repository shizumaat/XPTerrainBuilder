import SwiftUI
import SceneryKit

/// Library mode's side pane (RULINGS 2026-11-10j; spec §14; #2007, owner
/// 2026-11-11), top to bottom: the data folder, the disk budget (the
/// first item after it: everything the app keeps fits in it, caches
/// included), the patch library and Convert existing tiles near the top,
/// then Caches as one line (total, Clear…, Details…). The tiles table is
/// above the map (`LibraryTilesSection`, `ModeMainSplit`). The Qt window's
/// `O4_Qt_Modes.LibraryPane` is the same.
struct LibraryPane: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var storage = StorageModel()

    var body: some View {
        VStack(spacing: 0) {
            Text(AppMode.library.title)
                .scaledFont(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    DataFolderRow(model: storage)
                    DiskBudgetSection(model: storage)
                    Divider()
                    PatchLibrarySection()
                    ConvertTilesSection()
                    Divider()
                    CachesLine(model: storage)
                }
                .padding(10)
            }
        }
        .onAppear { storage.refresh(buildModel) }
    }
}

/// Settings ▸ Storage's pointer to Library mode (Qt: `LibraryPointer`).
struct StoragePointer: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        Section {
            HStack {
                Text(AppModeText.storagePointer)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                Button(AppModeText.storagePointerButton) {
                    buildModel.appMode.mode = .library
                }
            }
        }
    }
}
