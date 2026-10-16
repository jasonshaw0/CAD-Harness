# CAD-Harness documentation

CAD-Harness includes a reusable CAD framework and Studio, the application that
uses it with your IDE assistant. Both connect Python source and built geometry
to explicit engineering evidence.

Command guides show Windows/PowerShell first. Or on Linux/macOS, start with
`python3 bootstrap.py`, use `./.venv/bin/python` for the checkout environment,
and run `npm`/`npx` directly. The CLI arguments and Studio browser URL are the
same; platform-specific shell and path differences are noted in each guide.

| I want to… | Start here |
| --- | --- |
| Install, update or remove CAD-Harness | [Installation and compatibility](INSTALLATION.md) |
| Try real geometry, a failed check and its repair | [Packaged demonstration](DEMO.md) |
| Design with an assistant and live 3D canvas | [Studio](STUDIO.md) |
| Connect Codex or Claude Desktop | [MCP host setup](MCP_HOSTS.md) |
| Wrap my build123d model and add checks | [Project authoring](GETTING_STARTED.md) |
| Review generated source manually before execution | [Design workflow](DESIGN_WORKFLOW.md) |
| Run commands, configure MCP, or diagnose discovery | [CLI and MCP](CLI_MCP.md) |
| Measure holes, clearances, and sampled thickness | [Geometry measurements](MEASUREMENTS.md) |
| Understand the shared design and evidence pipeline | [Architecture](ARCHITECTURE.md) |
| Find moved code or reuse an older workspace | [Migration](MIGRATION.md) |
| Develop, test, or package CAD-Harness | [Contributing](../CONTRIBUTING.md) |
| Prepare GitHub beta downloads | [Release procedure](RELEASING.md) |
| Resume release and adoption work | [Release readiness and roadmap](RELEASE_READINESS.md) |
| Evaluate defect detection and design trials | [Evaluation](EVALUATION.md) |

The authoring contract is `cadharness.toml` → trusted Python factory →
`CADDocument`. Studio adds a structured brief, retained attempts, assistant
selection context, and a live viewer around that same contract. It uses the
framework's operations and measurement engine.

For assistant authors: [brief and coverage contracts](../src/cadharness/workflow/CONTRACTS.md)
and [manual design-loop instructions](../src/cadharness/workflow/prompts/workflow.md).
The [prototype acceptance record](STUDIO_ACCEPTANCE.md) retains historical
observations and paths; use the setup guides for current commands.
