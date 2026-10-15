# IDE design loop

Use `cadharness design` for the manual review workflow. Studio provides the same evidence engine through MCP with session authorization; follow its tool contract in that mode. It calls no model. Never infer hardware
dimensions from a family name alone. Read the prompt, brief, source, and existing
evidence before editing.

1. Extract dimensions, original units, interfaces, coordinate frame, fabrication
   constraints, provenance, assumptions, and measurable acceptance criteria into
   the brief. Preserve clarification answers in `clarifications.md` in the run.
2. Ask only blocking questions. Do not import candidate Python to inspect it.
   Missing or contradictory units and unspecified critical interfaces block the
   affected design. Keep physical evidence explicitly unverified.
3. Generate named parametric build123d source and a conventional `CADDocument`.
   Printable components use `printable-part`; reference envelopes stay separate.
   Use only reviewed local helpers, the standard library, build123d, and cadharness.
4. Review the manifest and every local input listed by `check --review-hashes`.
   Inspect imports and top-level actions. This review is a trust decision, not a
   sandbox guarantee. Pass the current source and accepted brief hashes to `check`
   only after review. Do not automate review by piping the hashes straight back.
5. Read `run.json`, verification results, and the actual/expected measurement
   evidence. A kernel error is not evidence of a dimensional failure. Resolve
   ambiguous selectors only when the intent supports the narrower selection.
6. Use `revise` before repairing geometry. Keep the accepted brief unchanged.
   Repair from measured causes, not screenshots alone. Do not remove checks,
   relax bounds, redefine selectors, or relabel evidence to obtain a pass.
7. Stop at one candidate plus two repairs, 120 seconds per build, 15 minutes
   active work, or unchanged failed source. Supply authoring/review time through
   `--active-seconds`; exclude time awaiting user replies. Preserve failed work.
8. Present `review.md`, editable source, brief, measurements, assumptions, and
   inspector. A ready-for-review design is not physically validated. Export only
   on request; keep reference envelopes out of manufacturing exports.

The mounting-plate template has illustrative dimensions. The assistant performs
language interpretation; the runner does not extract requirements from prose.
Unsupported evidence remains unknown or not-yet-verified. For a changed design
intent, create a new numbered brief, explain the change, and use `revise --brief`.
