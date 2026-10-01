"""Parser for Copilot MCP configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import MCPServer, ToolName

COPILOT_HOME = Path.home() / ".config" / "github-copilot" / "apps.json"


def parse_copilot_json(path: Path) -> list[MCPServer]:
    """Parse Copilot MCP servers from a JSON config file."""
    servers = []
    if not path.exists():
        return servers

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return servers

    # Copilot config has integrations with mcpServers
    integrations = data.get("integrations", {})
    for integration in integrations.values():
        mcp_servers = integration.get("mcpServers", {})
        for name, cfg in mcp_servers.items():
            server = _make_server(name, cfg, ToolName.COPILOT, str(path))
            if server:
                servers.append(server)

    return servers


def _make_server(
    name: str,
    cfg: dict | str,
    tool: ToolName,
    source: str,
) -> Optional[MCPServer]:
    """Create an MCPServer from a config dict."""
    if isinstance(cfg, str):
        return MCPServer(name=name, command=cfg, tool=tool, source=source)

    command = cfg.get("command", "")
    if not command:
        return None

    args = tuple(cfg.get("args", []))
    env_items = cfg.get("env", {})
    env = tuple(sorted(env_items.items())) if isinstance(env_items, dict) else ()

    return MCPServer(
        name=name,
        command=command,
        args=args,
        env=env,
        tool=tool,
        source=source,
    )


def get_copilot_servers() -> list[MCPServer]:
    """Get all Copilot MCP servers."""
    return parse_copilot_json(COPILOT_HOME)
