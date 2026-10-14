# cadharness

Experimental framework for agent-centric CAD workflows.

The architecture and product decisions are documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The two-part enclosure in [`examples/project-box`](examples/project-box) demonstrates the project, inspection, and validation contract.

## Quick Start

```powershell
python -m pip install -e .
cadharness list .
cadharness inspect examples/project-box
cadharness validate examples/project-box
```

All commands return versioned JSON. Export is explicit and refuses accidental overwrite by default. The optional local MCP server is installed with `python -m pip install -e ".[mcp]"` and launched with `cadharness-mcp`; project execution is limited to roots in `CADHARNESS_PROJECT_ROOTS` (or the launch working directory when the variable is unset).

Project entrypoints are trusted Python code. The root restriction is a path boundary, not a sandbox.

## Methodology / Why LLMs suck at CAD

Text, images, audio, and video tolerate approximation: a plausible output is an acceptable one. CAD doesn't, because the result is graded against physics, not perception.

**Errors compound.** If each of $n$ design decisions is correct with probability $p$, the whole model works with probability $p^n$. At $p = 0.99$ and $n = 200$, that's $\approx 13\%$. Tolerances stack the same way: worst-case error is $\sum t_i$, so a 0.2 mm slip per feature adds up fast.

**Constraints are global, generation is local.** The model emits code token by token, but the geometry must satisfy clearance, interference, and wall-thickness constraints all at once. A choice on line 12 can silently break line 180, and nothing in next-token prediction checks it.

**No spatial feedback.** The model reasons about 3D space through a 1D stream of code and never sees the result. Annotated parametric models with design intent are also scarce compared to text and images.

So this repo doesn't trust the output. Everything is source-backed, inspected, and validated.
