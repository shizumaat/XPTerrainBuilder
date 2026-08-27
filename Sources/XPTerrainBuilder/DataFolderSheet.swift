import SwiftUI
import AppKit

/// First-launch prompt for the data folder: where downloaded imagery,
/// elevation data, caches and built scenery tiles are stored. The engine
/// receives the choice as ORTHO4XP_DATA_ROOT; it stays changeable in
/// Settings ▸ General.
struct DataFolderSheet: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var showingPicker = ViewState(false)
    @StateObject private var chosenPath = ViewState(DataFolderSheet.defaultPath)

    static var defaultPath: String {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("XPTerrainBuilderData").path
    }

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "externaldrive.badge.checkmark")
                .font(.system(size: 44))
                .foregroundStyle(.tint)
            Text("Choose a Data Folder")
                .font(.title2.weight(.semibold))
            Text("XPTerrainBuilder stores downloaded imagery, elevation data, caches and built scenery tiles here. Builds can grow to tens of gigabytes, so pick a disk with plenty of free space. You can change this later in Settings.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)

            GroupBox {
                HStack {
                    Image(systemName: "folder.fill")
                        .foregroundStyle(.tint)
                    Text(chosenPath.value)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help(chosenPath.value)
                    Spacer()
                    Button("Choose…") { showingPicker.value = true }
                }
                .padding(6)
            }

            Button("Continue") { commit() }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
        }
        .padding(28)
        .frame(width: 480)
        .fileImporter(
            isPresented: $showingPicker.value,
            allowedContentTypes: [.folder]
        ) { result in
            if case .success(let url) = result {
                chosenPath.value = url.path
            }
        }
    }

    private func commit() {
        let url = URL(fileURLWithPath: chosenPath.value, isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        // Setting the pref dismisses the sheet (presented while it's empty).
        buildModel.dataRootPath = url.path
    }
}
