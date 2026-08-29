# Runway-crossing strict-claim law (owner review round, 2026-08-29)

Owner, on rebuilding HECA with 1.0.267: "identify how this node
(30.1076307,31.4094328) is being allowed on the runway edge 3 m lower
than the two adjacent nodes."

## Measured (owner's own patch, engine 1.50.1710, built 10:27)

- Runway 05C/23C ring (way -12210) node -31538 at idx 159: **108.54**
  between neighbours 111.08 / 111.07 — a 2.5 m pit in the runway edge.
  The node is SHARED with the crossing service corridor ring -12136
  (the drainage channel) whose descending profile owns that value.
- The census DOES price it: `within_shape runway|runway grade=101.53 %`
  — the SAME residual lane/hecar5 reported post-fix ("worst 680.71 →
  101.53 %, worst |de| 2.56 m") and the review (Fable) merged below the
  spec bar while reporting the tear fixed. The review failure is
  recorded; the bar was "zero tear rows, no vertex >0.05 m".
- LAW LEAK, measured: the crossing's runway|runway rows carry **cap
  8.0 %** while runway rows 22-30 m away carry the lawful 1.5 %. The
  round-5 contact-cap scoping stripped the corridor's way-level 1 % tag
  (built for the APRON case), and the per-station cap vector derives
  ONLY from apron adjacency — at a RUNWAY crossing nothing re-caps the
  stations, so the corridor (and the pairs its shared nodes form with
  the runway ring) solved and priced at the free 8 % class.
- Writer at the shared node: [WHO_WROTE — filled at dispatch].

## Laws

1. STRICT-CLAIM AT SHARED NODES: a solved node claimed by a runway-
   family role and any other family takes the RUNWAY family's LAW and
   VALUE — the strictest claimant wins, unconditionally (this is the
   free-road ruling's "conforms to the strictest" applied at node
   granularity, and protected transit: nothing may cut a runway).
   Generalised: strictest-claimant-wins at every shared node
   (runway > taxiway family > apron > road).
2. A CONTACT IS A VALUE QUESTION, NEVER A CAP QUESTION (owner
   2026-08-29c, verbatim intent: "a service corridor joining an apron
   should not be any different than a runway: it should exactly match
   the airside elevation — why would it need to be re-capped?"). At any
   airside pavement a corridor/road meets or crosses — runway, taxiway,
   apron alike — the corridor takes the airside elevation EXACTLY over
   the contact span (law 1's strict claim, by value). The 1 %/8 % cap
   classes govern only the FREE RUN between contacts; no cap machinery
   arbitrates a contact, and no re-capping at crossings is designed.
3. The census prices runway-family pairs at runway law regardless of
   which shape's read attributes the row — cap 8.0 on a runway|runway
   pair is structurally impossible (twin).

## Acceptance (SITE-FIRST — the owner's coordinate is the bar)

- Node -31538's class: the runway-edge node at 30.1076307,31.4094328
  within 0.05 m of its ring neighbours; ZERO runway-family rows over
  cap at the crossing (the 101.53 % row GONE, not reduced).
- No runway|runway row anywhere carries a cap other than the runway's.
- HECA census not worsened; controls byte-identical or attributed.
- The acceptance is re-measured on an APP-EQUIVALENT build frame, and
  the report quotes the owner-coordinate numbers FIRST.
