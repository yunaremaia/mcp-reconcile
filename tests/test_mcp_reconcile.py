"""Tests for mcp-reconcile."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mcp_reconcile.models import MCPServer, ToolName, DriftType
from mcp_reconcile.tools.claude import parse_claude_json
from mcp_reconcile.tools.cursor import parse_cursor_json
from mcp_reconcile.tools.codex import parse_codex_toml


class TestMCPServerModel:
    """Test MCPServer data model."""
    
    def test_version_extraction_with_at_v(self):
        server = MCPServer(
            name="github",
            command="npx",
            args=("-y", "@modelcontextprotocol/server-github@v1.2.0"),
        )
        assert server.version == "v1.2.0"
    
    def test_version_extraction_without_version(self):
        server = MCPServer(
            name="local",
            command="python",
            args=("-m", "my_server"),
        )
        assert server.version is None
    
    def test_full_command(self):
        server = MCPServer(
            name="github",
            command="npx",
            args=("-y", "@modelcontextprotocol/server-github"),
        )
        assert server.full_command == "npx -y @modelcontextprotocol/server-github"


class TestClaudeParser:
    """Test Claude Code config parsing."""
    
    def test_parse_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text("")
        assert parse_claude_json(path) == []
    
    def test_parse_missing_file(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        assert parse_claude_json(path) == []
    
    def test_parse_servers(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github@v1.2.0"],
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                    "env": {"DEBUG": "true"},
                },
            }
        }
        path = tmp_path / "claude.json"
        path.write_text(json.dumps(config))
        
        servers = parse_claude_json(path)
        assert len(servers) == 2
        
        github = [s for s in servers if s.name == "github"][0]
        assert github.command == "npx"
        assert github.tool == ToolName.CLAUDE
        assert github.version == "v1.2.0"
        
        filesystem = [s for s in servers if s.name == "filesystem"][0]
        assert filesystem.env == (("DEBUG", "true"),)


class TestCursorParser:
    """Test Cursor config parsing."""
    
    def test_parse_servers(self, tmp_path: Path):
        config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github@v1.1.0"],
                },
            }
        }
        path = tmp_path / "mcp.json"
        path.write_text(json.dumps(config))
        
        servers = parse_cursor_json(path)
        assert len(servers) == 1
        assert servers[0].tool == ToolName.CURSOR
        assert servers[0].version == "v1.1.0"


class TestCodexParser:
    """Test Codex config parsing."""
    
    def test_parse_toml(self, tmp_path: Path):
        content = """
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github@v1.0.0"]
"""
        path = tmp_path / "config.toml"
        path.write_text(content)
        
        servers = parse_codex_toml(path)
        assert len(servers) == 1
        assert servers[0].name == "github"
        assert servers[0].tool == ToolName.CODEX
        assert servers[0].version == "v1.0.0"


class TestDriftDetection:
    """Test drift detection logic."""
    
    def test_no_drift_single_server(self):
        from mcp_reconcile.scanner import scan_all, get_servers_by_name
        from mcp_reconcile.models import ScanResult
        
        result = ScanResult()
        result.servers = [
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.0.0"),
                tool=ToolName.CLAUDE,
            ),
        ]
        result.drifts = []
        assert not result.has_drift
    
    def test_version_drift_detection(self):
        from mcp_reconcile.reconcile import detect_drift
        from mcp_reconcile.models import ScanResult
        
        result = ScanResult()
        result.servers = [
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.2.0"),
                tool=ToolName.CLAUDE,
            ),
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.1.0"),
                tool=ToolName.CURSOR,
            ),
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.0.0"),
                tool=ToolName.CODEX,
            ),
        ]
        
        drifts = detect_drift(result)
        version_drifts = [d for d in drifts if d.drift_type == DriftType.VERSION]
        assert len(version_drifts) >= 1
        
        # Canonical should be Claude (highest priority)
        assert drifts[0].canonical.tool == ToolName.CLAUDE
        assert drifts[0].canonical.version == "v1.2.0"


class TestFixPlanGeneration:
    """Test fix plan generation."""
    
    def test_fix_plan_for_version_drift(self):
        from mcp_reconcile.reconcile import detect_drift, generate_fix_plan
        from mcp_reconcile.models import ScanResult
        
        result = ScanResult()
        result.servers = [
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.2.0"),
                tool=ToolName.CLAUDE,
            ),
            MCPServer(
                name="github",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github@v1.1.0"),
                tool=ToolName.CURSOR,
            ),
        ]
        
        drifts = detect_drift(result)
        plan = generate_fix_plan(drifts)
        
        # Should generate update operations for the stale ones
        assert len(plan) >= 1
        assert any(op["action"] == "update_version" for op in plan)
