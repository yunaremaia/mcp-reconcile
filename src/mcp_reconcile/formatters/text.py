"""Human-readable text formatter for drift output."""
from __future__ import annotations

from .models import Drift, DriftType, ScanResult


def format_scan_result(result: ScanResult) -> str:
    """Format scan results as human-readable text."""
    lines = []
    
    if not result.servers:
        lines.append("No MCP servers found in any tool configuration.")
        return "\n".join(lines)
    
    lines.append(f"Found {result.server_count} servers across {result.tool_count} tools")
    lines.append("")
    
    if not result.drifts:
        lines.append("No drift detected. All MCP configurations are in sync.")
        return "\n".join(lines)
    
    lines.append(f"Drift detected: {len(result.drifts)} issue(s)")
    lines.append("")
    
    for drift in result.drifts:
        lines.append(format_drift(drift))
        lines.append("")
    
    return "\n".join(lines)


def format_drift(drift: Drift) -> str:
    """Format a single drift entry."""
    lines = []
    
    if drift.drift_type == DriftType.VERSION:
        lines.append(f"DRIFT (version): {drift.server_name}")
        if drift.canonical:
            lines.append(f"  Canonical: {drift.canonical.tool.value} -> {drift.canonical.full_command}")
        for server in drift.drifts:
            lines.append(f"  {server.tool.value:12s} -> {server.full_command}")
    
    elif drift.drift_type == DriftType.MISSING:
        lines.append(f"DRIFT (missing): {drift.server_name}")
        for server in drift.drifts:
            lines.append(f"  Present in: {server.tool.value}")
    
    elif drift.drift_type == DriftType.ORPHAN:
        lines.append(f"DRIFT (orphan): {drift.server_name}")
        for server in drift.drifts:
            lines.append(f"  Only in: {server.tool.value} ({server.source})")
    
    elif drift.drift_type == DriftType.ARGS:
        lines.append(f"DRIFT (args): {drift.server_name}")
        if drift.canonical:
            lines.append(f"  Canonical: {drift.canonical.full_command}")
        for server in drift.drifts:
            lines.append(f"  {server.tool.value:12s} -> {server.full_command}")
    
    elif drift.drift_type == DriftType.COMMAND:
        lines.append(f"DRIFT (command): {drift.server_name}")
        for server in drift.drifts:
            lines.append(f"  {server.tool.value:12s} -> {server.command} {' '.join(server.args)}")
    
    elif drift.drift_type == DriftType.ENV:
        lines.append(f"DRIFT (env): {drift.server_name}")
        for server in drift.drifts:
            env_str = ", ".join(f"{k}={v}" for k, v in server.env)
            lines.append(f"  {server.tool.value:12s} -> {env_str}")
    
    return "\n".join(lines)
