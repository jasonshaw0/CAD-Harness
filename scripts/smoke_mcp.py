"""Exercise the installed cadharness MCP server through a real stdio client."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def smoke() -> dict:
    environment = os.environ.copy()
    environment["CADHARNESS_PROJECT_ROOTS"] = str(ROOT)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cadharness.mcp_server"],
        env=environment,
        cwd=ROOT,
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            initialization = await session.initialize()
            tools = await session.list_tools()
            validation = await session.call_tool(
                "validate_cad_project",
                {"project_path": "examples/project-box"},
            )
            structured = validation.structured_content or {}
            tool_names = [tool.name for tool in tools.tools]
            expected_tools = {
                "build_cad_inspector",
                "list_cad_schemas",
                "list_cad_projects",
                "inspect_cad_project",
                "validate_cad_project",
                "snapshot_cad_project",
                "compare_cad_project",
                "preview_cad_project",
                "export_cad_project",
            }
            if initialization.server_info.name != "cadHarness":
                raise RuntimeError(f"unexpected server name: {initialization.server_info.name}")
            if set(tool_names) != expected_tools:
                raise RuntimeError(f"unexpected tool surface: {tool_names}")
            if validation.is_error or not structured.get("passed"):
                raise RuntimeError(f"validation smoke test failed: {validation}")
            return {
                "server": initialization.server_info.name,
                "tools": tool_names,
                "validation": {
                    "is_error": bool(validation.is_error),
                    "project_id": structured.get("project_id"),
                    "passed": structured.get("passed"),
                    "variant": structured.get("variant"),
                    "summary": structured.get("summary"),
                },
            }


if __name__ == "__main__":
    print(json.dumps(anyio.run(smoke), indent=2, sort_keys=True))
