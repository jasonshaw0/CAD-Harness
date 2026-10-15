# cadHarness documentation

cadHarness includes a reusable CAD framework and Studio, the application that
uses it with your IDE assistant. Both connect Python source and built geometry
to explicit engineering evidence.

| I want to… | Start here |
| --- | --- |
| Design with an assistant and live 3D canvas | [Studio](STUDIO.md) |
| Wrap my build123d model and add checks | [Project authoring](GETTING_STARTED.md) |
| Review generated source manually before execution | [Design workflow](DESIGN_WORKFLOW.md) |
| Run commands, configure MCP, or diagnose discovery | [CLI and MCP](CLI_MCP.md) |
| Measure holes, clearances, and sampled thickness | [Geometry measurements](MEASUREMENTS.md) |
| Understand the shared design and evidence pipeline | [Architecture](ARCHITECTURE.md) |
| Find moved code or reuse an older workspace | [Migration](MIGRATION.md) |
| Develop, test, or package cadHarness | [Contributing](../CONTRIBUTING.md) |
| Evaluate defect detection and design trials | [Evaluation](EVALUATION.md) |

The authoring contract is `cadharness.toml` → trusted Python factory →
`CADDocument`. Studio adds a structured brief, retained attempts, assistant
selection context, and a live viewer around that same contract. It uses the
framework's operations and measurement engine.

For assistant authors: [brief and coverage contracts](../src/cadharness/workflow/CONTRACTS.md)
and [manual design-loop instructions](../src/cadharness/workflow/prompts/workflow.md).
The [prototype acceptance record](STUDIO_ACCEPTANCE.md) retains historical
observations and paths; use the setup guides for current commands.
