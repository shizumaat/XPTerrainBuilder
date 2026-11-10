import SwiftUI
import SceneryKit

/// Library mode's side pane (RULINGS 2026-11-10j; spec §14, lane U1),
/// top to bottom: the built tiles (the Library window until 10j), Storage
/// with the disk budget (moved from Settings, which keeps a pointer) and
/// the patch library. The Qt window's `O4_Qt_Modes.LibraryPane` is the
/// same.
struct LibraryPane: View {
    @EnvironmentObject var buildModel: BuildModel

    var body: some View {
        VStack(spacing: 0) {
            Text(AppMode.library.title)
                .scaledFont(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    LibraryTilesSection()
                    Form { StorageSection() }
                        .formStyle(.grouped)
                        .scrollDisabled(true)
                        .frame(minHeight: 320)
                    PatchLibrarySection()
                }
                .padding(10)
            }
        }
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
