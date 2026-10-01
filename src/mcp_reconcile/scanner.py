"""Core scanner that reads all tool configurations."""
from __future__ import annotations

from .models import MCPServer, ScanResult, ToolName
from .tools.claude import get_claude_servers
from .tools.codex import get_codex_servers
from .tools.copilot import get_copilot_servers
from .tools.cursor import get_cursor_servers
from .tools.vscode import get_vscode_servers
from .tools.windsurf import get_windsurf_servers


def scan_all() -> ScanResult:
    """Scan all supported tools and return collected servers."""
    result = ScanResult()

    scanners = [
        ("Claude Code", get_claude_servers),
        ("Cursor", get_cursor_servers),
        ("Copilot", get_copilot_servers),
        ("Codex", get_codex_servers),
        ("Windsurf", get_windsurf_servers),
        ("VS Code", get_vscode_servers),
    ]

    for tool_name, scanner_fn in scanners:
        try:
            servers = scanner_fn()
            result.servers.extend(servers)
        except Exception as e:
            result.errors.append(f"Failed to scan {tool_name}: {e}")

    return result


def get_servers_by_name(result: ScanResult) -> dict[str, list[MCPServer]]:
    """Group servers by name."""
    grouped: dict[str, list[MCPServer]] = {}
    for server in result.servers:
        if server.name not in grouped:
            grouped[server.name] = []
        grouped[server.name].append(server)
    return grouped


def get_servers_by_tool(result: ScanResult) -> dict[ToolName, list[MCPServer]]:
    """Group servers by tool."""
    grouped: dict[ToolName, list[MCPServer]] = {}
    for server in result.servers:
        if server.tool not in grouped:
            grouped[server.tool] = []
        grouped[server.tool].append(server)
    return grouped
