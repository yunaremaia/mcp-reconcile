"""Drift detection and reconciliation logic."""
from __future__ import annotations

from typing import Optional

from .models import Drift, DriftType, MCPServer, ScanResult, ToolName
from .scanner import get_servers_by_name, get_servers_by_tool


def detect_drift(result: ScanResult) -> list[Drift]:
    """Detect all drift in a scan result."""
    drifts: list[Drift] = []
    grouped = get_servers_by_name(result)
    
    for name, servers in grouped.items():
        # Orphan: only one server of this name
        if len(servers) == 1:
            server = servers[0]
            # Check if this tool is one of many configured tools
            all_tools = {s.tool for s in result.servers}
            if len(all_tools) > 1:
                drifts.append(Drift(
                    server_name=name,
                    drift_type=DriftType.ORPHAN,
                    description=f"Server '{name}' only in {server.tool.value}, missing from other tools",
                    drifts=[server],
                ))
            continue
        
        # Multiple servers with same name - check for drift
        canonical = _find_canonical(servers)
        
        # Check version drift
        versions = {s.version for s in servers if s.version is not None}
        if len(versions) > 1:
            drifts.append(Drift(
                server_name=name,
                drift_type=DriftType.VERSION,
                description=f"Version drift: {', '.join(sorted(versions))}",
                canonical=canonical,
                drifts=[s for s in servers if s != canonical],
            ))
        
        # Check args drift
        args_sets = {s.args for s in servers}
        if len(args_sets) > 1:
            drifts.append(Drift(
                server_name=name,
                drift_type=DriftType.ARGS,
                description=f"Argument drift across {len(args_sets)} configurations",
                canonical=canonical,
                drifts=[s for s in servers if s.args != canonical.args] if canonical else servers,
            ))
        
        # Check command drift
        commands = {s.command for s in servers}
        if len(commands) > 1:
            drifts.append(Drift(
                server_name=name,
                drift_type=DriftType.COMMAND,
                description=f"Command drift: {', '.join(sorted(commands))}",
                canonical=canonical,
                drifts=[s for s in servers if s.command != canonical.command] if canonical else servers,
            ))
        
        # Check env drift
        env_sets = {s.env for s in servers}
        if len(env_sets) > 1:
            drifts.append(Drift(
                server_name=name,
                drift_type=DriftType.ENV,
                description=f"Environment variable drift across {len(env_sets)} configurations",
                canonical=canonical,
                drifts=[s for s in servers if s.env != canonical.env] if canonical else servers,
            ))
    
    return drifts


def _find_canonical(servers: list[MCPServer]) -> Optional[MCPServer]:
    """Find the canonical (preferred) server configuration.
    
    Priority: Claude Code > Cursor > Copilot > Codex > Windsurf > VS Code
    """
    priority = [
        ToolName.CLAUDE,
        ToolName.CURSOR,
        ToolName.COPILOT,
        ToolName.CODEX,
        ToolName.WINDSURF,
        ToolName.VSCODE,
    ]
    
    for tool in priority:
        for server in servers:
            if server.tool == tool:
                return server
    
    return servers[0] if servers else None


def generate_fix_plan(drifts: list[Drift]) -> list[dict]:
    """Generate a list of fix operations from detected drifts."""
    operations = []
    
    for drift in drifts:
        if drift.drift_type == DriftType.VERSION and drift.canonical:
            for server in drift.drifts:
                operations.append({
                    "action": "update_version",
                    "tool": server.tool.value,
                    "server": server.name,
                    "from": server.version,
                    "to": drift.canonical.version,
                    "source": server.source,
                })
        
        elif drift.drift_type == DriftType.MISSING and drift.canonical:
            # Find which tools don't have this server
            for server in drift.drifts:
                operations.append({
                    "action": "add_server",
                    "tool": server.tool.value,
                    "server": server.name,
                    "from_tool": drift.canonical.tool.value,
                    "source": server.source,
                })
        
        elif drift.drift_type == DriftType.ORPHAN and drift.canonical:
            # Orphan = only in one tool, copy to all others
            operations.append({
                "action": "propagate",
                "server": drift.server_name,
                "from_tool": drift.canonical.tool.value,
                "source": drift.canonical.source,
            })
        
        elif drift.drift_type in (DriftType.ARGS, DriftType.COMMAND, DriftType.ENV) and drift.canonical:
            for server in drift.drifts:
                operations.append({
                    "action": "update_config",
                    "tool": server.tool.value,
                    "server": server.name,
                    "from": server.full_command,
                    "to": drift.canonical.full_command,
                    "source": server.source,
                })
    
    return operations
