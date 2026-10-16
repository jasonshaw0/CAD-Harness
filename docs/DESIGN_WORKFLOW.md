# Manual design workflow

For a live 3D canvas driven by your IDE assistant, start with
[CAD-Harness Studio](STUDIO.md). The manual CLI below remains available
for explicit source review and independent evidence collection.

Turn a prompt into reviewed parametric source, independent CAD checks, and a
portable review package. The assistant interprets language and edits Python;
the manual commands invoke no model or AI backend. Python source is the
editable authority. STEP/STL are explicit delivery artifacts.

Use the installed environment from [CLI setup](CLI_MCP.md#install-from-a-checkout). No extra
dependency is required. Run commands from the repository root.

## Try the bounded example

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m cadharness design init --id my-mount --prompt-file src/cadharness/workflow/benchmarks/prompts/square-mount.txt --case square-mount
& $python -m cadharness design check runs/my-mount/revisions/r001 --review-hashes
```

Or in Linux/macOS Bash/Zsh, set `python=./.venv/bin/python` and replace
`& $python` with `"$python"` throughout this guide. For example:
`"$python" -m cadharness design check runs/my-mount/revisions/r001 --review-hashes`.
Replace `Invoke-Item PATH` with `open PATH` on macOS or `xdg-open PATH` on a
Linux desktop to view the same generated HTML reports.

Read `prompt.txt`, `brief-v001.json`, the manifest, and **every candidate input**
listed in the hash output. Inspect imports and top-level actions before executing
Python. The template dimensions and hardware envelopes are illustrative.

After reviewing the source and accepting the brief, paste the two actual hashes:

```powershell
& $python -m cadharness design check runs/my-mount/revisions/r001 --reviewed-source SOURCE_HASH --accepted-brief BRIEF_HASH --active-seconds 60
Invoke-Item runs/my-mount/revisions/r001/review.html
```

`--active-seconds` records authoring and source-review time for this attempt;
worker time is measured automatically. Exclude waits for user answers. Without
that input, only build/check time is metered; no end-to-end speed claim is made.

For a real prompt, omit `--case`. The scaffold deliberately starts **blocked**.
The IDE assistant must extract requirements, ask blocking questions, complete the
brief, and generate appropriate source. Copying a benchmark brief does not
establish that a different prompt has been understood. Follow
[the IDE instructions](../src/cadharness/workflow/prompts/workflow.md) and [the contracts](../src/cadharness/workflow/CONTRACTS.md).

## Repair from evidence

To demonstrate failure, set `modeled_hole_count: int = 3` in the first candidate
before reviewing/executing it. The independent requirement still expects four.
Read `run.json`, `review.html`, and the validation evidence, then:

```powershell
& $python -m cadharness design revise runs/my-mount/revisions/r001
```

Edit only the new `r002/project/` source, restoring the missing hole. Review its
current hashes and execute `check` again. Do not relax acceptance criteria to
repair geometry. Old source and evidence remain available. Evaluated attempts
cannot be overwritten. Changes to prior source/evidence are rejected as stale.

For an intentional design change, create `brief-v002.json`, increment its
`revision`, explain the change, and use `revise ... --brief brief-v002.json`.
Existing brief revisions are locked after their first accepted check.

Default limits are one candidate plus two repairs per brief, 120 seconds per
worker, and 15 minutes of recorded active work. An unchanged failed source stops
the loop. Failures, ambiguity, and timeouts retain a review package.

## Review and export

The package contains ordinary Python, a manifest, original prompt and frozen
brief copies, a four-state requirement ledger, CAD-Harness JSON evidence, SVG
previews, an HTML inspector, and source/artifact hashes. Success means **ready
for user review**, not physical validation. A CAD-Harness pass alone cannot
override missing mandatory evidence or blocking questions.

```powershell
& $python -m cadharness design export runs/my-mount/revisions/r002 --format step
& $python -m cadharness design export runs/my-mount/revisions/r002 --format stl --component plate
```

Exports require current, ready-for-review evidence and a matching rebuilt
geometry fingerprint. Only `printable-part` components may be selected; reference
envelopes are excluded. Export receipts link file hashes to the evaluated source
and pre-export geometry identity. Existing exports are not overwritten.

## Supported boundaries

- First domain: one flat rectangular/circular plate, simple parallel cylindrical
  through-holes, square/circular patterns, and optional reference envelopes.
- Bounded expansion fixtures: an illustrative flange and simple two-part box.
  Box walls and skirt clearance are sampled or measured in an explicit Z slab;
  this does not establish global minimum thickness or physical fit.
- Unsupported or external requirements remain unknown or not-yet-verified.
  No threads, universal feature recognition, stress analysis, process
  qualification, or manufacturing certification is implied.

This is **reviewed local Python execution, without sandboxing**. Hashes record
what was reviewed; they do not inspect intent, prevent malicious Python, or
authenticate against a hostile local user. Workers receive a small environment
allowlist without provider credentials, but execute under the user's account.
They can access files and the network. Project paths and output restrictions do
not isolate code. Only use reviewed imports and trusted installed dependencies.

The workflow does not change MCP roots or configuration. Configure narrow,
explicit roots for any existing CAD-Harness MCP use. The CLI/Python runner uses
the same measurement and check implementation; it adds orchestration and a
coverage ledger, not another geometry kernel or validation system.

## Verification and evaluation

Install `.[mcp,studio]` to run all tests, including Studio's API integration
checks. The manual workflow itself still needs no extra dependency.

```powershell
& $python -m unittest discover -s tests -v
& $python -m cadharness.workflow.benchmarks --output runs/benchmark-001
```

The repeatable benchmark preserves six baseline trials, realistic seeded
defects, repairs, a named-parameter edit, and blocked ambiguous prompts. It must
detect every seeded defect, produce no false-ready verdict, and complete at
least five of six baseline trials. Repairs retain the same brief hash.

**This benchmark uses scripted source mutations and repairs.** It measures the
runner's detection and provenance, not a model's ability to interpret prompts.
For AI evaluation, conduct three fresh IDE trials per plate prompt; capture
first/final correctness, actual repair count, authoring/review time, clarification
answers, unresolved assumptions, and a timed manual baseline. Do not claim AI
success or speed improvement from scripted trials. [Evaluation details](EVALUATION.md).

Browser QA uses Playwriter exclusively. [The browser check](../scripts/verify_workflow_browser.js)
opens a saved review package, exercises inspector filters/anchors, checks SVG
loading, and saves desktop/mobile screenshots. Read the Playwriter skill before
using it.

## Studio and deferred interfaces

The optional [Studio application](STUDIO.md) exposes source-backed design
tools to the IDE assistant through MCP, with no separate model calls. Its previous
Codex CLI designer is opt-in. Both use trusted local execution. Hosted/local model adapters,
untrusted-code isolation, and unattended deployment remain deferred. Existing
CAD-Harness public schemas remain unchanged.
