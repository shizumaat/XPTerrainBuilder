import SceneryKit
import SwiftUI

/// The Gateway airports question (#1989; the Qt window's
/// `O4_Qt_Gateway_Airports.GatewayAirportsBox`, same copy): one checkbox
/// per airport the engine offers, every one checked when it opens, each
/// with its explanation. Install sends the checked ICAOs and every one
/// shown.
struct GatewayAirportsSheet: View {
    let offer: O4GatewayAirports
    /// `(action, icaos)`: "install" with the checked ICAOs, "never", or nil
    /// (Not now).
    let answer: (String?, [String]) -> Void
    @State private var checked: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(O4GatewayAirportsCopy.title).font(.headline)
            Text(O4GatewayAirportsCopy.body).fixedSize(horizontal: false, vertical: true)
            ForEach(offer.offers) { item in
                VStack(alignment: .leading, spacing: 2) {
                    Toggle(item.title, isOn: Binding(
                        get: { checked.contains(item.icao) },
                        set: { on in
                            if on { checked.insert(item.icao) } else { checked.remove(item.icao) }
                        }))
                    Text(item.detail)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .padding(.leading, 20)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Text(O4GatewayAirportsCopy.detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button(O4GatewayAirportsCopy.neverButton) { answer("never", []) }
                Spacer()
                Button(O4GatewayAirportsCopy.notNowButton, role: .cancel) { answer(nil, []) }
                    .keyboardShortcut(.cancelAction)
                Button(O4GatewayAirportsCopy.installButton) {
                    answer("install", offer.offers.map(\.icao).filter(checked.contains))
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onAppear { checked = Set(offer.offers.map(\.icao)) }
    }
}

/// The Gateway airports question on the map window (#1989). A modifier
/// of its own so `MapMainView.body` stays within the compiler's
/// type-check budget.
struct GatewayAirportsPrompt: ViewModifier {
    @ObservedObject var buildModel: BuildModel

    func body(content: Content) -> some View {
        content
            .sheet(item: Binding(
                get: { buildModel.gatewayAirportsPrompt },
                set: { _ in }
            )) { offer in
                GatewayAirportsSheet(offer: offer) { action, icaos in
                    buildModel.answerGatewayAirportsPrompt(action: action, icaos: icaos)
                }
            }
    }
}
