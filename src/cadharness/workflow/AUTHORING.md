# CAD-Harness authoring guide — version 1

CAD-Harness supplies this workflow through MCP. No personal skill, browser
extension, desktop-control permission, or external CAD viewer is required.
The host's assistant authors source; CAD-Harness builds, measures and displays it.

## Design intent and source

- Inspect existing source and requirements before changing a design. Preserve
  unrelated work and keep ordinary Python/TOML as the editable authority.
- Use named build123d parameters, millimeters unless explicitly specified,
  an explicit coordinate frame, stable component IDs, and readable features.
  Keep separate manufactured parts separate; fuse features of one physical part.
- Check relationships between dimensions. Ask about genuinely blocking
  contradictions or interfaces; choose and disclose noncritical defaults.
  Distinguish user statements, calculations, defaults and unverified assumptions.
- Encode required dimensions and interfaces as geometry-derived checks where
  supported. A supplied parameter is not a measurement. Report unsupported or
  unresolved requirements explicitly. Valid topology alone does not prove intent.

## MCP design loop

1. Read `studio_status`, create/open a design, and start a turn for the user's
   instruction. Read `studio_get_context(include_contract=True)` before first
   authoring; it includes the source API and frozen-brief contract.
2. Submit complete Python/TOML files and the structured brief. Read
   `studio_get_job` until terminal, then inspect measurements and failures.
   Studio displays built revisions while source remains editable.
3. Repair actual causes with the same turn and omit the brief. Keep its criteria
   frozen. The existing initial-candidate-plus-two-repairs budget still applies;
   never manufacture another user turn to evade it. Changed source may improve a
   passing candidate within that budget, including after a visual finding.
4. Use meaningful construction stages when useful, but do not deliberately fail
   requirements solely to obtain progress pictures. Images do not consume build
   attempts, change geometry readiness, approve a design, or authorize exports.
5. Present editable source, actual checks, relevant observations and remaining
   assumptions. Export STEP/STL only when requested. Computational evidence does
   not establish physical fit, safety, comfort or manufacturing suitability.

MCP startup authorizes trusted local Python execution within configured roots;
it does not sandbox Python or claim human source review. The separate manual
`design check` workflow requires explicit source/brief review hashes. Do not add
those manual approval steps to the already-authorized MCP workflow.

## Adaptive visual inspection

Use `studio_render_view` when seeing the model will answer a meaningful question.
There is no screenshot quota, required review form, or additional completion gate.

- Exact checks may suffice for simple, fully characterized primitives or small
  dimensional edits whose geometry is otherwise unchanged.
- Inspect uncertain blends, sweeps, hollow interiors, complex cutouts, assemblies,
  obscured interfaces, unexpected proportions or placement, and substantial shape
  changes. Visual review supplements exact geometry measurements.
- Start with one informative view. Use top/front/right/left/bottom views, selected
  components, or model-space focus bounds to resolve specific remaining questions.
  Inspect relevant subassemblies rather than every part indiscriminately.
- Reinspect affected features after a meaningful correction. Stop when further
  views add no information; avoid unchanged views and pictures of every step.
- Name the revision explicitly when inspecting an earlier or failed build.
  Render metadata identifies the scene used. Failed builds with no scene cannot
  be inspected; an older scene is never evidence for the failed candidate.
- Studio uses a separate scene and camera. The user's viewport, selection,
  visibility and theme do not determine the image and are not changed by capture.
- If capture is unavailable, preserve the build and report the missing visual
  check only when one was needed. Do not launch browsers, ask for desktop control,
  retry repeatedly, or claim to have seen an image that was not returned.
- Only an image-capable model can visually inspect an image. Text-only models
  may request images for a person or another model, but must not claim inspection.
  Captured images are not automatic review records. Use ordinary assistant
  messages to record useful observations without overstating what was checked.
