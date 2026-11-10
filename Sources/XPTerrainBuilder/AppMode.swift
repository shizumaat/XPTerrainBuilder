import SwiftUI
import SceneryKit

/// The app's three modes, Build · Fly · Library (RULINGS 2026-11-10j;
/// spec `flight-manager-and-world-20261110.md` §14). One map and one
/// selection; the side pane follows the mode. The Qt window's
/// `O4_App_Modes` / `O4_Qt_Modes` hold the same keys, words and offer rule
/// (`Ortho4XP/tests/test_app_modes.py` keeps the two equal).
enum AppMode: String, CaseIterable, Identifiable {
    case build, fly, library

    var id: String { rawValue }
    /// The segment's word (the glossary's `mode_<mode>`).
    var title: String { O4Glossary.term("mode_" + rawValue) }

    /// The remembered mode, or Build for anything unknown.
    static func restore(_ raw: String?) -> AppMode {
        raw.flatMap(AppMode.init(rawValue:)) ?? .build
    }
}

/// The words of the modes (`O4_App_Modes` holds the same).
enum AppModeText {
    static let flyPlaceholder = "Flights come here: name a flight plan and the app makes the scenery for it. Until then, the line below follows X-Plane and sharpens the imagery around you."
    static let offerText = "X-Plane has a flight loaded."
    static let offerOpen = "Open Fly"
    static let offerDismiss = "Not now"
    static let storagePointer = "The data folder's sizes, Clear and the disk budget's use are in Library."
    static let storagePointerButton = "Show in Library"
}

/// The current mode (remembered) and the "Open Fly" offer: when X-Plane
/// answers with a flight loaded while the app is in another mode, the
/// app OFFERS Fly and never switches by itself. "A flight loaded" is read
/// from the imagery follow job's status (X-Plane's Web API answers and
/// positions arrive); a new flight load offers again.
@MainActor
final class AppModeModel: ObservableObject {
    @Published var mode: AppMode {
        didSet {
            guard mode != oldValue else { return }
            UserDefaults.standard.set(mode.rawValue, forKey: PrefKeys.appMode)
            if mode == .fly { dismissOffer() }
        }
    }
    @Published private(set) var offerShown = false
    private var loaded = false
    private var loads = 0

    init() {
        mode = AppMode.restore(UserDefaults.standard.string(forKey: PrefKeys.appMode))
    }

    /// X-Plane answers with a flight loaded (positions arrive).
    static func flightLoaded(state: String, xplane: Bool) -> Bool {
        xplane && (state == "following" || state == "paused")
    }

    /// Every follow status; `O4_App_Modes.FlyOffer.observe` is the same.
    func observe(_ status: O4ImageryFollowStatus) {
        let isLoaded = Self.flightLoaded(state: status.state, xplane: status.xplane)
        let newFlight = isLoaded && (!loaded || status.flightLoads > loads)
        if newFlight, mode != .fly { offerShown = true }
        if !isLoaded || mode == .fly { offerShown = false }
        loaded = isLoaded
        loads = max(loads, status.flightLoads)
    }

    /// "Not now" (or "Open Fly"): hidden until the next flight.
    func dismissOffer() {
        offerShown = false
    }
}

/// The mode switch leading the map toolbar.
struct ModeSwitch: View {
    @ObservedObject var model: AppModeModel

    var body: some View {
        Picker("Mode", selection: $model.mode) {
            ForEach(AppMode.allCases) { mode in
                Text(mode.title).tag(mode)
            }
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .help("Build tiles, fly with the scenery made for your flight, or manage what you keep")
    }
}

/// The offer to open Fly, above the side pane in Build and Library.
struct FlyOfferBanner: View {
    @ObservedObject var model: AppModeModel

    var body: some View {
        if model.offerShown, model.mode != .fly {
            HStack(spacing: 8) {
                Image(systemName: "airplane.departure")
                Text(AppModeText.offerText)
                    .scaledFont(.callout)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 4)
                Button(AppModeText.offerOpen) {
                    model.dismissOffer()
                    model.mode = .fly
                }
                .controlSize(.small)
                .buttonStyle(.borderedProminent)
                Button(AppModeText.offerDismiss) { model.dismissOffer() }
                    .controlSize(.small)
            }
            .padding(8)
            .background(.quaternary.opacity(0.4))
        }
    }
}
