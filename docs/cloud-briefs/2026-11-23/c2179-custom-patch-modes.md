# Lane c2179: custom patch, two modes for 1.0 (#2179; RULINGS 2026-11-23d, 23f)

Read `common.md` and `Ortho4XP/docs/specs/custom-patch-choice-2179-spec.md`. The spec's Blend is OUT (#2260).
Implement lanes L1, L2 and L4 with two modes only:
- **As made**: the patch unchanged, on the elevation it was made for. **Our auto patch**: high-resolution data.
- Default (23f, replaces the spec's §5.2): an installed custom patch is As made, with a warning that
  higher-resolution data is available but requires the auto patch. No coverage test picks the mode.
- One reader `O4_Custom_Patches.use_of/uses`; a picker on the Build card's airport row and tile info replaces
  "Use auto patch", Mac and Qt together. Retire the 19b re-base and band (L4), keeping `_pick_reference`.
KASE evidence and the integration build wait for the Mac; use the spec's synthetic twins.
