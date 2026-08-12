import Testing
import Foundation
@testable import SceneryKit

/// The provider sign-in half of the engine protocol (1.5): the
/// `auth_providers` descriptor and the `SignInResult` event.
///
/// Wire shapes are copied from the engine's own tests
/// (Ortho4XP/tests/test_engine_provider_signin.py) — the event class names
/// ARE the wire names, matched here as string literals, so these fixtures
/// are the drift alarm.
@Suite struct ProviderSignInTests {
    private func object(_ json: String) -> [String: Any]? {
        (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String: Any]
    }

    @Test func signInResultEventParsing() {
        let ok = object(#"{"event":"SignInResult","session_name":"dgterritorio","ok":true,"error_text":"","seq":4,"ts":1.0}"#)
            .flatMap { O4Event.parse(object: $0) }
        #expect(ok == .signInResult(sessionName: "dgterritorio", ok: true, errorText: ""))

        let failed = object(#"{"event":"SignInResult","session_name":"dgterritorio","ok":false,"error_text":"The identity provider rejected the sign-in.","seq":5,"ts":2.0}"#)
            .flatMap { O4Event.parse(object: $0) }
        #expect(failed == .signInResult(sessionName: "dgterritorio", ok: false,
                                        errorText: "The identity provider rejected the sign-in."))
    }

    @Test func providerAccountDescriptorParsing() throws {
        let json = O4JSON.from(try #require(object(#"""
        {"session_name":"dgterritorio","codes":["PORTUGAL2M","PORTUGALTIDAL"],
         "attribution":"Direcao-Geral do Territorio","credential_kind":"session",
         "login_url":"https://cdd.dgterritorio.gov.pt/auth/login",
         "registration_url":"https://cdd.dgterritorio.gov.pt/auth/login",
         "service_host":"cdd.dgterritorio.gov.pt","setup_steps":[],
         "credential_store_available":true,"signed_in":true,
         "username":"user@example.org","status_text":"Signed in as user@example.org",
         "status_pending":false}
        """#)))
        let account = try #require(O4ProviderAccount(json: json))
        #expect(account.id == "dgterritorio")
        #expect(account.codes == ["PORTUGAL2M", "PORTUGALTIDAL"])
        #expect(account.isAPIKey == false)
        #expect(account.title == "Direcao-Geral do Territorio")
        #expect(account.sheetTitle == "Direcao-Geral do Territorio")
        #expect(account.signedIn)
        #expect(account.statusText == "Signed in as user@example.org")
        #expect(account.statusPending == false)
    }

    @Test func apiKeyDescriptorCarriesSetupStepsAndHostTitle() throws {
        let json = O4JSON.from(try #require(object(#"""
        {"session_name":"dataforsyningen","codes":["DENMARK40CM"],"attribution":"",
         "credential_kind":"api_key","login_url":"","registration_url":"https://dataforsyningen.dk/",
         "service_host":"dataforsyningen.dk",
         "setup_steps":["Create a free account at https://dataforsyningen.dk/.","Copy the token."],
         "credential_store_available":true,"signed_in":false,"username":"",
         "status_text":"No API key","status_pending":true}
        """#)))
        let account = try #require(O4ProviderAccount(json: json))
        #expect(account.isAPIKey)
        // No attribution: the row falls back to the account name, the sheet
        // title to the service host (the Qt dialog's own rule).
        #expect(account.title == "dataforsyningen")
        #expect(account.sheetTitle == "dataforsyningen.dk")
        #expect(account.setupSteps.count == 2)
        #expect(account.statusPending)
    }

    /// A descriptor without the one required key is dropped, not faked.
    @Test func descriptorWithoutSessionNameIsRejected() throws {
        let json = O4JSON.from(try #require(object(#"{"codes":["X"],"signed_in":true}"#)))
        #expect(O4ProviderAccount(json: json) == nil)
    }
}
