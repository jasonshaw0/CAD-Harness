# Studio interface acceptance — 2026-10-15

The Studio interface follows the supplied v2 concept: a light canvas with opaque
floating panels, restrained blue accents, a compact bottom dock, an unbranded
header, and a full dark theme. The application uses real CAD meshes, measurements,
revision records, source files, and exports. Demonstration data and destructive
source-removal controls from the concept were omitted from the application.

## Repeat the browser walkthrough

Build the frontend and start a dedicated test instance:

```powershell
npm --prefix studio/web run build
.\.venv\Scripts\python.exe -m cadharness studio --workspace runs/studio-browser --port 8743
```

Or on Linux/macOS, keep the npm build command and start the server with
`./.venv/bin/python -m cadharness studio --workspace runs/studio-browser --port 8743`.

Read the Playwriter skill and create a task session. In another terminal, from
the repository root:

```powershell
cmd /d /s /c npx -y playwriter@latest session new --tab-group cadharness
cmd /d /s /c npx -y playwriter@latest -s SESSION_ID --timeout 30000 -f scripts/verify_studio_browser.js
```

Or on Linux/macOS, omit `cmd /d /s /c` and run `npx` directly in both commands.

Repeat the file invocation until it reports `done`. Each call performs one
action, prints a snapshot and browser logs, and advances state. Inspect results
between calls. Set `state.studioUrl` through a Playwriter snippet for another
port; `state.studioArtifacts` selects an absolute artifact directory. The script
creates a fresh example, rebuilds, and explicitly exports STEP. Use a test
workspace, not a user's active session. Screenshots and the exchange file stay
under ignored `runs/` by default.

## Observed behavior

- A real mounting-plate build produced three component meshes and passed all
  37 requirements. Properties showed 60 × 60 × 4 mm and the measured volume;
  selecting `plate` also reached the MCP viewer/context record.
- Isolation, visibility, engineering detail expansion, and attention filtering
  worked. Rebuild produced r002, history displayed r001, and Return to current
  restored r002. Comparison correctly reported no changes for an unchanged rebuild.
- Source previews fetched the retained manifest/Python. Export produced an
  actual STEP file containing only the printable plate; Chrome reported a
  completed download and the endpoint returned a valid `ISO-10303-21` document.
- Light/dark screenshots were inspected at 1440 × 960. Source-panel, fitted
  model, and standard-view screenshots were inspected at 390 × 844. Panels
  scroll within the viewport, the dock remains reachable, and portrait Fit
  accounts for the camera aspect ratio.
- Switching saved designs updated the MCP viewer record. Reload restored the
  active MCP design even with a stale browser design preference; theme and
  viewport preferences also persisted across reloads.
- TypeScript and the production build passed. The 20 Studio/API/real-MCP tests
  passed, including failed measurement, frozen-brief repair, continuation, and
  STL export. No model service was invoked for these fixture checks.
- A second browser instance used a deterministic local fixture in optional Codex
  mode. In-app composition built the real fixture, cancellation retained r001,
  New design cleared the prior design context, and clarification questions
  appeared in activity. This checked the UI path without invoking Codex or a
  model service.

The browser profile emitted extension messaging/CSP diagnostics. The first
Playwriter download-copy attempt also lost its relay temporary file; subsequent
Chrome download completion and a same-browser response check confirmed the
application transfer. The walkthrough retains an evidence copy through that
browser session rather than depending on the relay's `saveAs` temporary file.

Local artifacts from this implementation pass are under `runs/ui-overhaul/`.
They are generated QA evidence and are not part of the distribution.
