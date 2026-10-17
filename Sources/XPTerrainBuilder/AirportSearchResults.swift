import SwiftUI
import SceneryKit

/// The search field's live result list (issue #543): airports by code or
/// name, `CODE · Name · City, Country`, best match then largest first
/// (SceneryKit `AirportSearch`, the rule the Qt window shares), or one
/// "No airport matches" row. Drawn over the map's top-right corner, under
/// the toolbar field, so typing never loses focus to a popover.
struct AirportSearchResults: View {
    @ObservedObject var text: ViewState<String>
    let search: AirportSearch
    /// Whether the text is something else the field handles — a tile key
    /// or a list of codes — which shows no airport list.
    let handledElsewhere: (String) -> Bool
    let onPick: (GlobalAirport) -> Void

    var body: some View {
        let query = text.value
        if AirportSearch.normalize(query).unicodeScalars.count >= AirportSearch.minQueryLength,
           !handledElsewhere(query) {
            list(query: query, results: search.results(for: query))
        }
    }

    private func list(query: String, results: [GlobalAirport]) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            if results.isEmpty {
                Text(AirportSearch.noMatchText(query))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
            }
            ForEach(Array(results.enumerated()), id: \.offset) { _, airport in
                Button {
                    onPick(airport)
                } label: {
                    Text(AirportSearch.resultLabel(code: airport.icao, name: airport.name,
                                                   city: airport.city, country: airport.country))
                        .lineLimit(1)
                        .truncationMode(.tail)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .font(.callout)
        .frame(width: 340, alignment: .leading)
        .padding(.vertical, 4)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .shadow(radius: 6)
        .padding(.top, 8)
        .padding(.trailing, 12)
    }
}
