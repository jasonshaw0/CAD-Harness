"""Portable MCP client configuration generation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Iterable


def mcp_client_config(
    roots: Iterable[str | Path] = (".",), *, name: str = "cadharness",
    studio: bool = False, studio_workspace: str | Path | None = None, studio_port: int = 8741,
) -> dict[str, Any]:
    """Return a client config that does not depend on the host working directory."""
    resolved_roots = [str(Path(root).expanduser().resolve()) for root in roots]
    if not resolved_roots:
        raise ValueError("at least one MCP project root is required")
    if not name.strip():
        raise ValueError("MCP server name cannot be empty")
    if not 0 <= studio_port <= 65535:
        raise ValueError("Studio port must be between 0 and 65535")
    if studio_workspace is not None and not studio:
        raise ValueError("--studio-workspace requires --studio")

    args = ["-m", "cadharness.mcp_server"]
    for root in resolved_roots:
        args.extend(("--root", root))
    if studio:
        args.append("--studio")
        if studio_workspace is not None:
            workspace = Path(studio_workspace).expanduser().resolve()
            if not any(workspace.is_relative_to(Path(root)) for root in resolved_roots):
                raise ValueError("Studio workspace must be inside an explicit trusted root")
            args.extend(("--studio-workspace", str(workspace)))
        if studio_port != 8741:
            args.extend(("--studio-port", str(studio_port)))
    return {
        "mcpServers": {
            name: {
                "command": sys.executable,
                "args": args,
            }
        }
    }


__all__ = ["mcp_client_config"]
