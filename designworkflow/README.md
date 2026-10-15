# IDE-assisted design workflow

Turn a prompt into reviewed parametric source, independent CAD checks, and a
portable review package. The assistant interprets language and edits Python;
this checkout-local tool invokes no model or AI backend. Python source is the
editable authority. STEP/STL are explicit delivery artifacts.

Use this checkout's installed environment (see the root README). No extra
dependency is required. Run commands from the repository root.

## Try the bounded example

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m designworkflow init --id my-mount --prompt-file designworkflow/benchmarks/prompts/square-mount.txt --case square-mount
& $python -m designworkflow check designworkflow/runs/my-mount/revisions/r001 --review-hashes
```

Read `prompt.txt`, `brief-v001.json`, the manifest, and **every candidate input**
listed in the hash output. Inspect imports and top-level actions before executing
Python. The template dimensions and hardware envelopes are illustrative.

After reviewing the source and accepting the brief, paste the two actual hashes:

```powershell
& $python -m designworkflow check designworkflow/runs/my-mount/revisions/r001 --reviewed-source SOURCE_HASH --accepted-brief BRIEF_HASH --active-seconds 60
Invoke-Item designworkflow/runs/my-mount/revisions/r001/review.html
```

`--active-seconds` records authoring and source-review time for this attempt;
worker time is measured automatically. Exclude waits for user answers. Without
that input, only build/check time is metered; no end-to-end speed claim is made.

For a real prompt, omit `--case`. The scaffold deliberately starts **blocked**.
The IDE assistant must extract requirements, ask blocking questions, complete the
brief, and generate appropriate source. Copying a benchmark brief does not
establish that a different prompt has been understood. Follow
[the IDE instructions](prompts/workflow.md) and [the contracts](CONTRACTS.md).

## Repair from evidence

To demonstrate failure, set `modeled_hole_count: int = 3` in the first candidate
before reviewing/executing it. The independent requirement still expects four.
Read `run.json`, `review.html`, and the validation evidence, then:

```powershell
& $python -m designworkflow revise designworkflow/runs/my-mount/revisions/r001
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
brief copies, a four-state requirement ledger, CADHarness JSON evidence, SVG
previews, an HTML inspector, and source/artifact hashes. Success means **ready
for user review**, not physical validation. A CADHarness pass alone cannot
override missing mandatory evidence or blocking questions.

```powershell
& $python -m designworkflow export designworkflow/runs/my-mount/revisions/r002 --format step
& $python -m designworkflow export designworkflow/runs/my-mount/revisions/r002 --format stl --component plate
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
explicit roots for any existing CADHarness MCP use. The CLI/Python runner uses
the same measurement and check implementation; it adds orchestration and a
coverage ledger, not another geometry kernel or validation system.

## Verification and evaluation

```powershell
& $python -m unittest discover -s tests -v
& $python -m unittest discover -s designworkflow/tests -v
& $python -m designworkflow.benchmarks --output designworkflow/runs/benchmark-001
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
success or speed improvement from scripted trials. [Evaluation details](benchmarks/README.md).

Browser QA uses Playwriter exclusively. [The browser check](benchmarks/review-browser.js)
opens a saved review package, exercises inspector filters/anchors, checks SVG
loading, and saves desktop/mobile screenshots. Read the Playwriter skill before
using it.

## Deferred interfaces

No callable IDE model is assumed. A later unattended adapter must explicitly
select supported credentials, model, provider, costs/limits, and isolation before
running unreviewed source. Codex CLI, a hosted API, or a local model are options,
not current dependencies. Add a local application only after review friction
justifies it. Existing CADHarness public schemas remain unchanged.
