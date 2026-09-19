"""Parser for Claude Code MCP configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import MCPServer, ToolName

# Default config paths
CLAUDE_HOME = Path.home() / ".claude.json"
CLAUDE_PROJECT = Path.cwd() / ".mcp.json"


def parse_claude_json(path: Path) -> list[MCPServer]:
    """Parse Claude Code MCP servers from a JSON config file."""
    servers = []
    if not path.exists():
        return servers
    
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return servers
    
    # Global MCP servers
    mcp_servers = data.get("mcpServers", {})
    for name, cfg in mcp_servers.items():
        server = _make_server(name, cfg, ToolName.CLAUDE, str(path))
        if server:
            servers.append(server)
    
    # Project-level servers (also in mcpServers key for .mcp.json)
    project_servers = data.get("mcpServers", {})
    if project_servers and str(path) == str(CLAUDE_PROJECT):
        for name, cfg in project_servers.items():
            server = _make_server(name, cfg, ToolName.CLAUDE, str(path))
            if server and server not in servers:
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
        # shorthand: just a command string
        return MCPServer(
            name=name,
            command=cfg,
            tool=tool,
            source=source,
        )
    
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


def get_claude_servers() -> list[MCPServer]:
    """Get all Claude Code MCP servers (global + project)."""
    servers = parse_claude_json(CLAUDE_HOME)
    if CLAUDE_PROJECT.exists():
        project_servers = parse_claude_json(CLAUDE_PROJECT)
        # Merge, avoiding duplicates (project servers take precedence for same name)
        existing_names = {s.name for s in servers}
        for s in project_servers:
            if s.name not in existing_names:
                servers.append(s)
    return servers
