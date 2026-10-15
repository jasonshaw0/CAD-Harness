# cadHarness Studio

Studio is the included application for the cadHarness framework. Your IDE
assistant authors designs through MCP; the browser displays built geometry,
revisions, and measured requirements.

Start with [Studio setup and controls](../docs/STUDIO.md). The Python application
lives in [`src/cadharness/studio/`](../src/cadharness/studio/); this directory
contains the editable frontend.

From the repository root:

```sh
npm --prefix studio/web ci
npm --prefix studio/web run build
```

The build places static assets in the Python package. For local development,
run the backend on port 8741 and `npm --prefix studio/web run dev`.
See [contributing](../CONTRIBUTING.md) for tests and distribution checks.
