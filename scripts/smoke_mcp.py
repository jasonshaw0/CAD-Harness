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
            structured = validation.structuredContent or {}
            return {
                "server": initialization.serverInfo.name,
                "tools": [tool.name for tool in tools.tools],
                "validation": {
                    "is_error": bool(validation.isError),
                    "project_id": structured.get("project_id"),
                    "passed": structured.get("passed"),
                    "summary": structured.get("summary"),
                },
            }


if __name__ == "__main__":
    print(json.dumps(anyio.run(smoke), indent=2, sort_keys=True))

