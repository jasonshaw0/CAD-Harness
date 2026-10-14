"""Exercise the installed cadharness MCP server through a real stdio client."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def smoke() -> dict:
    with tempfile.TemporaryDirectory() as unrelated_cwd:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "cadharness.mcp_server", "--root", str(ROOT)],
            cwd=unrelated_cwd,
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                initialization = await session.initialize()
                tools = await session.list_tools()
                status = await session.call_tool("get_cadharness_status", {})
                validation = await session.call_tool(
                    "validate_cad_project",
                    {"project_path": "examples/project-box"},
                )
                verification = await session.call_tool(
                    "verify_cad_project",
                    {"project_path": "examples/project-box"},
                )
                status_content = status.structured_content or {}
                structured = validation.structured_content or {}
                tool_names = [tool.name for tool in tools.tools]
                expected_tools = {
                    "get_cadharness_status",
                    "build_cad_inspector",
                    "list_cad_schemas",
                    "list_cad_projects",
                    "inspect_cad_project",
                    "validate_cad_project",
                    "verify_cad_project",
                    "snapshot_cad_project",
                    "compare_cad_project",
                    "preview_cad_project",
                    "export_cad_project",
                }
                if initialization.server_info.name != "cadHarness":
                    raise RuntimeError(
                        f"unexpected server name: {initialization.server_info.name}"
                    )
                if set(tool_names) != expected_tools:
                    raise RuntimeError(f"unexpected tool surface: {tool_names}")
                if status.is_error or status_content.get("project_count") != 2:
                    raise RuntimeError(f"status smoke test failed: {status}")
                if validation.is_error or not structured.get("passed"):
                    raise RuntimeError(f"validation smoke test failed: {validation}")
                verified = verification.structured_content or {}
                if verification.is_error or not verified.get("verification", {}).get("passed"):
                    raise RuntimeError(f"verification smoke test failed: {verification}")
                return {
                    "server": initialization.server_info.name,
                    "version": initialization.server_info.version,
                    "tools": tool_names,
                    "status": {
                        "project_count": status_content.get("project_count"),
                        "roots": status_content.get("roots"),
                    },
                    "validation": {
                        "is_error": bool(validation.is_error),
                        "project_id": structured.get("project_id"),
                        "passed": structured.get("passed"),
                        "variant": structured.get("variant"),
                        "summary": structured.get("summary"),
                    },
                    "verification": verified.get("verification"),
                }


if __name__ == "__main__":
    print(json.dumps(anyio.run(smoke), indent=2, sort_keys=True))
