"""Parser for VS Code MCP configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import MCPServer, ToolName

VSCODE_SETTINGS = Path.cwd() / ".vscode" / "settings.json"


def parse_vscode_json(path: Path) -> list[MCPServer]:
    """Parse VS Code MCP servers from settings.json."""
    servers = []
    if not path.exists():
        return servers
    
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return servers
    
    mcp_servers = data.get("mcp.servers", {})
    for name, cfg in mcp_servers.items():
        server = _make_server(name, cfg, ToolName.VSCODE, str(path))
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


def get_vscode_servers() -> list[MCPServer]:
    """Get all VS Code MCP servers."""
    return parse_vscode_json(VSCODE_SETTINGS)
