# Release readiness and adoption roadmap

Audit date: 2026-10-16. Baseline: `5ecaa3a` on `main`, package version `0.9.0`.
This is an incremental plan. Complete one milestone per session, record evidence
here, and stop before the next milestone. A passing computational check does
not establish physical fit, safety, strength, or manufacturing performance.

## Initial technical audit

The current architecture is a suitable foundation. Preserve the shared
framework operations, source-backed workflow, Studio, and stdio MCP transport.
No major rewrite, new geometry engine, model provider, or desktop shell is needed.

| Area | Observed state and adoption gap |
| --- | --- |
| Installation | `bootstrap.py` creates/reuses `.venv`, checks Python/Node, installs editable extras, runs `npm ci` and the canvas build, verifies NEMA17, and generates local MCP JSON. `--check` and `--framework-only` already exist. Differing config is preserved; no host settings are edited. |
| Supported paths | Checkout bootstrap, manual editable core, `[mcp]`, and `[mcp,studio]` installs are documented. Locally built wheels work outside the checkout. An index-based `pip install CAD-Harness` is **not** an established installation path; publication/name availability must be checked before advertising it. |
| Node dependency | React/Three.js/Vite source is in `studio/web`; Node 22.12+ and npm build static output into `src/cadharness/studio/web`. The Python server serves those files; normal wheel runtime does not invoke Node. Browser acceptance tooling separately uses Node/npx as a development dependency. |
| Package contents | Explicit setuptools package data includes contracts, versioned authoring guidance, prompts, benchmark prompts, three Python/TOML templates, and generated canvas/assets. Baseline wheel and sdist built successfully with these resources. A wheel built without the frontend can still be created, so a successful build alone is insufficient. |
| Source archive | Baseline sdist includes compiled Studio assets, but not editable `studio/web/src`, lockfile, example projects, full guides, or the checkout bootstrap. It can rebuild a Python wheel without Node; it is not a full contributor checkout. Decide source-archive completeness and dependency notice requirements before public distribution. |
| Existing smoke | `scripts/smoke_distribution.py` already installs a wheel into a temporary venv, serves frontend assets, checks aliases/resources, and runs real stdio fail/repair/follow-up/export and PNG transport tests outside the checkout. It originally borrowed development dependencies through a `.pth` file; that cannot prove clean dependency resolution. |
| Compatibility evidence | CI run [38904567289](https://github.com/jasonshaw0/CAD-Harness/actions/runs/38904567289) passed all nine jobs at the audit baseline: Python 3.11/3.12 on Windows/Linux/macOS; minimum build123d 0.13 on Linux; bootstrap/frontend/distribution on Linux/macOS; isolated Playwriter rendering on Linux. Declared Python 3.13/3.14 compatibility is not covered by that matrix. Windows full bootstrap/distribution was not in the frontend matrix. |
| MCP onboarding | Absolute interpreter/root generation, Studio-aware config, packaged authoring guide, diagnostics, port-conflict guidance, and shared Studio ownership already exist. Documentation gives generic `mcpServers` JSON; this is not a verified Codex TOML/CLI or Claude Desktop host setup guide. Real stdio SDK tests verify transport, not every host application's lifecycle. |
| First useful result | Clone → bootstrap → CLI `verify` and `inspector` provides genuine geometry evidence without an assistant. `missing-hole` gives an intentional failure. Studio can start standalone and build its existing example cases, but no `demo` CLI or packaged failure→repair walkthrough exists. Connecting an assistant still requires manual host setup. |
| Studio | Backend has loopback, same-origin and token checks, file-backed jobs/history, explicit session execution, frontend availability reporting and shared MCP service support. Frontend already has empty states, examples, isolation, measurements, history, source, comparison, downloads, themes and mobile controls. Reuse these for onboarding; preserve the existing design. |
| Verification | Unit/integration coverage includes geometry-derived defects, frozen briefs, unknown mandatory evidence, stale-source/evaluator rejection, immutable evaluated attempts, output containment, export fingerprints, source reloads and legacy v1 schemas. Parameter declarations and comparison are not substitutes for measured verification. |
| Presentation | README already leads with a real Studio screenshot, a short product explanation, a usable checkout quick start and physical-validation limits. CONTRIBUTING, CHANGELOG, migration and operational guides already exist. Preserve this direction; avoid another cosmetic rewrite. |
| Repository/release state | GitHub reports no license, topics or homepage. Description: “Source-backed CAD project inspection and engineering validation for build123d”. Default labels already include bug, enhancement, documentation, question, accessibility, help wanted and good first issue. No issue templates, release workflow, tags or GitHub releases were found. No historical LICENSE/COPYING/NOTICE file was found in local Git history. |

Reviewed: README, pyproject, bootstrap, contributing/changelog, all top-level
guides in `docs/`, asset provenance, migration shim, CLI/diagnostics/config,
MCP root handling, Studio backend/frontend/build config, CI, distribution and
acceptance scripts, test inventory and example/model source/metadata. The live
repository metadata and baseline CI jobs were read through GitHub CLI. Existing
untracked `assets/` and `p.url()))` are unrelated user files and are preserved.

### Demonstration candidates

| Example | Best use and limitation |
| --- | --- |
| NEMA17 / packaged mounting plate | First demonstration: measurable hole count/diameter/pattern, deliberate missing hole, frozen repair and export. Dimensions are illustrative assumptions, not a certified motor interface. |
| Project box / packaged enclosure | Second tutorial: separate printable parts, selected thickness samples, clearance and interference, revision comparison. Sampled walls do not establish a global minimum. |
| Pipe flange | Small optional rotational/pattern example. Already has a packaged template; no need for another engine feature. |
| Coffee mug | Sweeps, blends, hollow geometry and visual inspection. Existing README references a local saved design; that workspace is not shipped. |
| Pocket Cycloid | Hero/showcase for editable complexity and kinematic evidence. Expensive motion checks and untested print fit/friction make it a poor first-run smoke fixture. Keep the actual evidence and physical limits visible. |

## Decisions and prioritization

**Essential:** artifact completeness, genuinely clean installation, an evidence-
backed compatibility matrix, license/third-party notice review, and explicit
release controls. **High value:** host-specific onboarding, a deterministic
assistant-free demo, bug templates, install/update/uninstall guidance and beta
tester feedback. **Nice to have:** topics, a social preview, one CI badge and
community-specific drafts after installation works.

**Deferred:** native installers/bundlers (OCCT size, platform builds, signing,
updates and maintenance need user evidence), expanded tutorials and promotional
production before the demo stabilizes. **Rejected:** a fake demo frontend,
parallel setup systems, automatic trust-root expansion, relaxed verification
for a green demo, unnecessary providers/hosted services, and blanket UI rewrites.

### Owner decisions and external controls

- **License:** recommend considering Apache-2.0 for its explicit contributor
  patent grant and patent-litigation termination clause; it also requires
  redistribution/change notices and applicable NOTICE handling. MIT is shorter,
  requires preservation of copyright/license notices, and has no equivalent
  explicit patent clause. Both are permissive; the owner must choose terms and
  confirm copyright ownership and third-party obligations. Sources:
  [MIT](https://choosealicense.com/licenses/mit/) and
  [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
  Prepared change checklist: add the chosen complete official text as root
  `LICENSE`, confirm copyright attribution, set matching SPDX project metadata,
  include required notices in artifacts, and test wheel/sdist metadata. No
  license text or license metadata has been applied pending that decision.
- **Repository settings:** proposed description: “Editable build123d CAD with
  geometry-derived checks, revision evidence, a local 3D Studio, and MCP.”
  Topics: `build123d`, `parametric-cad`, `cad`, `engineering`, `python`, `mcp`,
  `cad-automation`, `opencascade`, `3d-printing`. Keep homepage empty until a
  maintained documentation/demo destination exists. Use a real Studio capture
  for a later social preview. These settings are proposals, not applied changes.
- **Publishing:** tags, public GitHub releases, PyPI/TestPyPI uploads, trusted
  publisher/account setup, and promotional posts require explicit authorization.
  CI artifact retention alone is not a public release or publication approval.

## Milestones and acceptance criteria

| Order / scope | Priority, dependencies and cost | Measurable acceptance |
| --- | --- | --- |
| **M1: Distribution validation foundation** (this session; B2/B4/E2 subset) | Essential; no owner decision; small tooling-only change, low runtime risk. Extend the existing smoke script and CI. | Build sdist then wheel from that sdist; compare source/resource bytes and version metadata; reject missing/stale assets; install extras with fresh dependencies; serve installed assets and run real stdio defect/repair/export tests outside checkout; retain validated artifacts with hashes. Existing fast smoke mode remains available. |
| **M2: Compatibility and install lifecycle** (next; B3/E1/E2) | Essential; depends on M1; medium CI/dependency work. | Test 3.13/3.14 dependency availability and practical CI coverage before widening claims; record exact supported combinations. Exercise core-only/full installs, reinstallation and upgrade with a retained saved workspace; document update/uninstall steps. Decide and document sdist source/third-party notice contents. No unsupported platform claims. |
| **M3: Supported MCP host setup** (C) | High value; depends on stable install; medium configuration risk. | Research actual Codex and Claude host formats/lifecycle; document and verify each supported path. Reuse `mcp-config`/doctor; preview and approve any host changes, preserve unrelated entries, handle escaping/collisions, and test restart/connection. No root widening. |
| **M4: Packaged first-use demonstration** (D plus focused F tutorials) | High value; depends on M1/M2; medium Studio integration risk. | Reuse templates, Studio and evidence formats for assistant-free real geometry, failure, repair, history/comparison, source and explicit export in a fresh dedicated workspace. No credentials. Verify packaged resources and inspect real Playwriter desktop/mobile output and logs. Preserve existing workspaces. |
| **M5: Public beta preparation** (A, remaining B4/E/F/G readiness) | Essential license/release controls; other presentation work high value/nice to have. Depends on M2–M4 and license decision. Split into small sessions. | Apply approved license and notices; align metadata/version/changelog; add practical issue forms and beta feedback checklist; refine links/install guide around validated paths; prepare tag/artifact/release-note checks and owner-controlled trusted publishing. Create tailored launch drafts only after a real demo. Review release candidate artifacts before requesting publication authorization. |

M5 prepares publication. Actual public release, PyPI upload and community posts
remain separate owner-authorized actions; do not infer approval from this plan.

## Compatibility constraints

- Keep `cadharness` imports, both console-script aliases, `cadharness.toml`,
  MCP keys/environment variables, stdio, saved workspace paths and v1 schema IDs.
  `CAD-Harness` and legacy `cadharness` are distinct distribution names; preserve
  the migration warning about competing ownership of scripts.
- Keep explicit trusted roots and local Python execution disclosures. No host
  settings, personal skills, active Studio workspace or saved hashes are rewritten.
- Keep unknown/unsupported requirements, source/geometry fingerprints, frozen
  briefs and strict export checks. Packaging success says nothing about physical
  engineering performance or autonomous model accuracy.
- Kernel/toolchain changes can invalidate exact geometry/evaluator evidence;
  retain old revisions and rebuild through the existing workflow, never patch hashes.

## Session record and resumption

### M1 — completed 2026-10-16

- [x] Audit current checkout, baseline CI, repository metadata and package contents.
- [x] Build baseline sdist and wheel; confirm existing assets/templates are included.
- [x] Extend existing smoke script with sdist→wheel checks, fresh dependency mode,
  artifact retention/hashes, and preservation of an existing output directory.
- [x] Add packaging fault tests and run them (4 tests passed).
- [x] Configure full bootstrap/distribution CI on Windows as well as Linux/macOS.
- [x] Finish fresh-install integration and broader regression checks.

Validation on Windows / Python 3.12.11 / build123d 0.13.0:

- Baseline: 157 tests passed in 167.239 s.
- Final discovery: **161 tests passed in 148.394 s**, including four new
  packaging fault tests (missing wheel/sdist resources, changed bytes, stale
  assets and version drift).
- Fresh wheel extras/dependency installation: `pip check` passed; installed
  frontend routes/assets and all four CLI aliases passed; **13 integration
  tests passed in 39.415 s** outside the checkout, including real stdio
  failure/repair/follow-up/STL export and shared MCP PNG transport.
- Both built artifacts matched **55 source/resource files**. Retained artifact
  hashes verified. Reusing the output directory exited 1 and left every byte
  unchanged.
- Frontend tests: **19 passed**, zero failures. Local documentation links:
  17 checked, none missing. `git diff --check` passed.

Local evidence: ignored `runs/release-audit-20261016-131121/` contains
`baseline-build.log`, `baseline-tests.log`, `final-tests.log`, `distribution.log`,
and `validated-dist/` (wheel, sdist, SHA256SUMS). These are local validation
artifacts, not published releases. The milestone's commit introduces this
record; consult its GitHub Actions run for the expanded platform CI outcomes.

No runtime/public API, schema, root, host configuration, model, frontend source
or saved-workspace changes were needed. Browser acceptance was not rerun locally;
the passing baseline CI rendering run is recorded above. Serving assets and MCP
PNG transport tests alone do not establish browser usability. Next: **M2 only**.

Known remaining limits: no license decision, no public package/release, no
validated 3.13/3.14 matrix, no host-specific automatic configuration, no bundled
demo command, no independent beta feedback. Setuptools currently emits warnings
about data directories being importable but excluded from package discovery;
archive inspection checks their actual inclusion. Do not silence those warnings
by casually changing namespace/package discovery.

To resume: read this file and `AGENTS.md`, inspect Git/user changes and the latest
CI results, then implement **M2 only**. Use current packaging/host documentation;
do not reconstruct old plans from chat or begin promotional work prematurely.
