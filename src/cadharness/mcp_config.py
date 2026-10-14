"""Portable MCP client configuration generation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Iterable


def mcp_client_config(
    roots: Iterable[str | Path] = (".",), *, name: str = "cadharness"
) -> dict[str, Any]:
    """Return a client config that does not depend on the host working directory."""
    resolved_roots = [str(Path(root).expanduser().resolve()) for root in roots]
    if not resolved_roots:
        raise ValueError("at least one MCP project root is required")
    if not name.strip():
        raise ValueError("MCP server name cannot be empty")

    args = ["-m", "cadharness.mcp_server"]
    for root in resolved_roots:
        args.extend(("--root", root))
    return {
        "mcpServers": {
            name: {
                "command": sys.executable,
                "args": args,
            }
        }
    }


__all__ = ["mcp_client_config"]
