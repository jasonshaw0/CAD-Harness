# Prototype acceptance — 2026-10-14

Executed in the Windows checkout with the installed, ChatGPT-authenticated Codex
CLI default model. These were fresh model requests and follow-ups, not replayed
artifact proposals. Raw requests, JSONL transcripts, proposals, and reported token
usage remain in ignored `designworkflow/runs/studio/jobs/`. Source, frozen briefs,
measurements, and revision outcomes remain in `designs/` within that workspace.

| Live design | Actual outcome |
| --- | --- |
| `design-aea10325`: 82 × 54 mm mounting plate, four through-holes | Initial integration failures preserved as r001–r003. Recovered r004 at 8 mm thickness and Ø4.8 mm holes; r005 follow-up increased thickness to 10 mm and moved centers to (±28, ±15). Both passed all 21 geometry requirements. |
| `design-3bdac24a`: skirted enclosure, 72 × 46 × 24 mm usable cavity | Actual base/lid displayed; 19 checks passed and eight unsupported mandatory measurements stayed unknown. Follow-up r004 raised cavity height to 28 mm and translated the lid, retaining 19 passes and eight unknowns. It was never labeled ready. |
| `design-4dbbf7a5`: plain 84 × 58 × 30 mm enclosure and flat lid | First brief used an invalid thickness report field; repairs preserved the brief and stopped on repeated source. Explicit follow-up corrected the binding without relaxing 3 mm limits and increased height to 34 mm. All 16 mandatory CAD requirements passed; optional physical performance remained unverified. Rebuilt r005 produced STEP/STL downloads for base and lid. |

Relevant real Codex jobs: `job-7dc545fc`, `job-6bf45326`, `job-239eb5d2`
(mount); `job-a45c3c7c`, `job-fda17f24` (skirted enclosure);
`job-a902111a`, `job-211ede32` (plain enclosure). Additional clarification job
`job-c9a4be4e` asked for the motor interface and attachment geometry instead of
inventing a NEMA 17 specification. A later live request was cancelled through the
UI; the owned Codex process stopped and the scene stayed labeled r005.

Playwriter exclusively exercised the built app in headless Chrome: actual canvas
picking, component selection/hide/isolation, orbit/pan/zoom/fit and standard-view
controls, ghosted references, revision history and overlay, actual/expected
measurements, requirement changes and unknowns, clarification, cancellation,
failure retaining its labeled scene, reopening after server restart, and source,
STEP, and STL downloads. Desktop and mobile screenshots were inspected. Captures,
browser scripts, downloaded files, test output, and `acceptance.json` remain under
`designworkflow/runs/studio/qa/`. Final stable interactions had no console errors.
Some Playwriter screenshot calls timed out; separate capture calls succeeded.

Single observed example open-to-scene times, including the native build, API, and
UI update: mount **3.433 s**, enclosure **3.424 s**, flange **3.431 s**. A source
rebuild and UI update took **3.319 s**. These are local observations, excluding
model generation, not a repeated performance benchmark or a manual-baseline
speedup claim.

Validation: **95 core tests + 34 workflow/Studio tests passed**, the real stdio
MCP smoke test passed, and TypeScript checking plus the production frontend build
passed. Vite reports the expected large Three.js bundle warning. Discovery tests
now tolerate incomplete candidate manifest error records while still requiring
all original example IDs.

Export acceptance exposed OCCT boolean operations changing serialized source
state for touching base/lid faces. Interference, clearance, and workflow slab
clipping now operate on copies; a regression checks unchanged source BREP
fingerprints. Export fingerprint gates remain enforced.

This prototype does not certify physical fit or manufacturing performance.
Unsupported cavity/face measurements remain unresolved. Model-authored briefs can
contain mistakes; a frozen invalid binding requires a new explicit intent turn
rather than an automatic relaxation. Trusted-session Python execution remains
local and unsandboxed. Full unattended reliability and repeated prompt benchmarks
remain outside this prototype acceptance.
