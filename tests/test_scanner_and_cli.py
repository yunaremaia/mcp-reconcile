"""Tests for the scanner, formatters, and CLI entry point.

These modules had no coverage at all: the other test module exercised the
per-tool parsers and the drift model, but nothing covered the code path a user
actually runs (`mcp-reconcile scan`), so a regression there would ship silently.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_reconcile import cli
from mcp_reconcile.formatters.json import format_scan_result as format_json
from mcp_reconcile.formatters.text import format_scan_result as format_text
from mcp_reconcile.models import Drift, DriftType, MCPServer, ScanResult, ToolName
from mcp_reconcile.scanner import get_servers_by_name, get_servers_by_tool, scan_all
from mcp_reconcile.tools.claude import parse_claude_json
from mcp_reconcile.tools.codex import parse_codex_toml
from mcp_reconcile.tools.copilot import parse_copilot_json
from mcp_reconcile.tools.cursor import parse_cursor_json
from mcp_reconcile.tools.vscode import parse_vscode_json
from mcp_reconcile.tools.windsurf import parse_windsurf_json


def _server(
    name: str,
    tool: ToolName,
    args: tuple[str, ...] = (),
    env: tuple[tuple[str, str], ...] = (),
    source: str = "",
) -> MCPServer:
    """Build a server entry for tests."""
    return MCPServer(name=name, command="npx", args=args, env=env, tool=tool, source=source)


@pytest.fixture
def isolated_configs(monkeypatch, tmp_path: Path) -> Path:
    """Point every tool parser at paths that do not exist.

    Without this the parsers read the developer's real ``~/.claude.json`` and
    friends, so the suite would depend on whatever happens to be installed on
    the machine running it.
    """
    absent = tmp_path / "absent"
    monkeypatch.setattr("mcp_reconcile.tools.claude.CLAUDE_HOME", tmp_path / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.claude.CLAUDE_PROJECT", absent / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.cursor.CURSOR_HOME", tmp_path / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.cursor.CURSOR_PROJECT", absent / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.codex.CODEX_HOME", tmp_path / "absent.toml")
    monkeypatch.setattr("mcp_reconcile.tools.copilot.COPILOT_HOME", tmp_path / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.vscode.VSCODE_SETTINGS", tmp_path / "absent.json")
    monkeypatch.setattr("mcp_reconcile.tools.windsurf.WINDSURF_HOME", tmp_path / "absent.json")
    return tmp_path


class TestScannerGrouping:
    """Test the grouping helpers that feed drift detection."""

    def test_get_servers_by_name_groups_duplicates(self):
        result = ScanResult(
            servers=[
                _server("github", ToolName.CLAUDE),
                _server("github", ToolName.CURSOR),
                _server("linear", ToolName.CLAUDE),
            ]
        )
        grouped = get_servers_by_name(result)
        assert set(grouped) == {"github", "linear"}
        assert len(grouped["github"]) == 2
        assert grouped["linear"][0].tool == ToolName.CLAUDE

    def test_get_servers_by_tool_groups_by_tool(self):
        result = ScanResult(
            servers=[
                _server("github", ToolName.CLAUDE),
                _server("linear", ToolName.CLAUDE),
                _server("github", ToolName.CURSOR),
            ]
        )
        grouped = get_servers_by_tool(result)
        assert set(grouped) == {ToolName.CLAUDE, ToolName.CURSOR}
        assert len(grouped[ToolName.CLAUDE]) == 2
        assert len(grouped[ToolName.CURSOR]) == 1

    def test_grouping_empty_result(self):
        result = ScanResult()
        assert get_servers_by_name(result) == {}
        assert get_servers_by_tool(result) == {}


class TestScanAll:
    """Test that scan_all aggregates every tool parser."""

    def test_collects_from_all_tools(self, monkeypatch, isolated_configs: Path):
        config = isolated_configs / "claude.json"
        config.write_text(
            json.dumps({"mcpServers": {"github": {"command": "npx", "args": ["-y", "pkg@v1.0.0"]}}})
        )
        monkeypatch.setattr("mcp_reconcile.tools.claude.CLAUDE_HOME", config)

        result = scan_all()
        assert result.errors == []
        assert [s.name for s in result.servers] == ["github"]
        assert result.servers[0].tool == ToolName.CLAUDE
        assert result.servers[0].source.endswith("claude.json")

    def test_no_configs_found_is_not_an_error(self, isolated_configs: Path):
        result = scan_all()
        assert result.servers == []
        assert result.errors == []
        assert result.has_drift is False

    def test_records_parser_failure_instead_of_raising(self, isolated_configs: Path, monkeypatch):
        """A broken config in one tool must not abort the whole scan."""

        def boom():
            raise RuntimeError("permission denied")

        monkeypatch.setattr("mcp_reconcile.scanner.get_claude_servers", boom)
        result = scan_all()
        assert result.servers == []
        assert len(result.errors) == 1
        assert "Claude Code" in result.errors[0]
        assert "permission denied" in result.errors[0]


class TestJsonFormatter:
    """Test the machine-readable output that CI consumers parse."""

    def test_empty_result(self):
        data = json.loads(format_json(ScanResult()))
        assert data["servers"] == []
        assert data["drifts"] == []
        assert data["summary"] == {
            "total_servers": 0,
            "total_tools": 0,
            "drift_count": 0,
            "has_drift": False,
        }
        assert data["errors"] == []

    def test_serializes_server_and_drift(self):
        canonical = _server("github", ToolName.CLAUDE, args=("-y", "pkg@v2.0.0"), env=(("K", "V"),))
        stale = _server("github", ToolName.CURSOR, args=("-y", "pkg@v1.0.0"))
        drift = Drift(
            server_name="github",
            drift_type=DriftType.VERSION,
            description="Version drift: v1.0.0, v2.0.0",
            canonical=canonical,
            drifts=[stale],
        )
        result = ScanResult(servers=[canonical, stale], drifts=[drift], errors=["boom"])

        data = json.loads(format_json(result))
        assert [s["name"] for s in data["servers"]] == ["github", "github"]
        assert data["servers"][0]["env"] == {"K": "V"}
        assert data["servers"][0]["tool"] == "claude"
        assert data["servers"][0]["args"] == ["-y", "pkg@v2.0.0"]
        assert data["drifts"][0]["drift_type"] == "version"
        assert data["drifts"][0]["canonical"]["tool"] == "claude"
        assert [s["tool"] for s in data["drifts"][0]["drifts"]] == ["cursor"]
        assert data["summary"] == {
            "total_servers": 2,
            "total_tools": 2,
            "drift_count": 1,
            "has_drift": True,
        }
        assert data["errors"] == ["boom"]


class TestTextFormatter:
    """Test the human-readable output."""

    def test_no_servers(self):
        assert "No MCP servers found" in format_text(ScanResult())

    def test_servers_without_drift(self):
        result = ScanResult(servers=[_server("github", ToolName.CLAUDE)])
        out = format_text(result)
        assert "Found 1 servers across 1 tools" in out
        assert "No drift detected" in out

    @pytest.mark.parametrize(
        ("drift_type", "marker"),
        [
            (DriftType.VERSION, "DRIFT (version)"),
            (DriftType.MISSING, "DRIFT (missing)"),
            (DriftType.ORPHAN, "DRIFT (orphan)"),
            (DriftType.ARGS, "DRIFT (args)"),
            (DriftType.COMMAND, "DRIFT (command)"),
            (DriftType.ENV, "DRIFT (env)"),
        ],
    )
    def test_renders_every_drift_type(self, drift_type: DriftType, marker: str):
        canonical = _server("github", ToolName.CLAUDE, args=("-y", "pkg@v2.0.0"))
        result = ScanResult(
            servers=[canonical],
            drifts=[
                Drift(
                    server_name="github",
                    drift_type=drift_type,
                    description="d",
                    canonical=canonical,
                    drifts=[_server("github", ToolName.CURSOR, args=("-y", "x"))],
                )
            ],
        )
        out = format_text(result)
        assert marker in out
        assert "Drift detected: 1 issue(s)" in out


class TestCli:
    """Test the CLI contract: exit codes and emitted output."""

    def _no_drift(self):
        return ScanResult(servers=[_server("github", ToolName.CLAUDE)])

    def _with_version_drift(self):
        canonical = _server("github", ToolName.CLAUDE, args=("-y", "pkg@v2.0.0"))
        stale = _server("github", ToolName.CURSOR, args=("-y", "pkg@v1.0.0"), source="/tmp/cfg.json")
        drift = Drift(
            server_name="github",
            drift_type=DriftType.VERSION,
            description="Version drift: v1.0.0, v2.0.0",
            canonical=canonical,
            drifts=[stale],
        )
        return ScanResult(servers=[canonical, stale], drifts=[drift])

    def test_no_command_prints_help(self, capsys):
        assert cli.main([]) == 0
        assert "usage:" in capsys.readouterr().out

    def test_scan_exits_zero_without_drift(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", self._no_drift)
        assert cli.main(["scan"]) == 0
        assert "No drift detected" in capsys.readouterr().out

    def test_scan_exits_one_on_drift_for_ci(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", self._with_version_drift)
        assert cli.main(["scan"]) == 1
        assert "DRIFT (version)" in capsys.readouterr().out

    def test_scan_json_output_is_parseable(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", self._no_drift)
        assert cli.main(["scan", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["has_drift"] is False
        assert payload["servers"][0]["name"] == "github"

    def test_fix_reports_nothing_to_do(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", ScanResult)
        assert cli.main(["fix", "--dry-run"]) == 0
        assert "No drift to fix." in capsys.readouterr().out

    def test_fix_dry_run_previews_operations(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", self._with_version_drift)
        assert cli.main(["fix", "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "update_version" in out
        assert "v2.0.0" in out

    def test_fix_without_flags_exits_one(self, monkeypatch, capsys):
        monkeypatch.setattr(cli.scanner, "scan_all", self._with_version_drift)
        assert cli.main(["fix"]) == 1
        assert "--dry-run" in capsys.readouterr().out

    def test_fix_apply_does_not_touch_config_files(self, monkeypatch, capsys, tmp_path: Path):
        """--apply is still a stub, so it must not claim success by rewriting configs."""
        config = tmp_path / "mcp.json"
        config.write_text(json.dumps({"mcpServers": {"github": {"command": "npx"}}}))
        before = config.read_text()

        def result_with_config_source():
            scan = self._with_version_drift()
            stale = scan.servers[1]
            return ScanResult(
                servers=[scan.servers[0], stale.__class__(**{**stale.__dict__, "source": str(config)})],
                drifts=scan.drifts,
            )

        monkeypatch.setattr(cli.scanner, "scan_all", result_with_config_source)
        assert cli.main(["fix", "--apply"]) == 0
        assert config.read_text() == before
        assert "APPLY" in capsys.readouterr().out


class TestRemainingToolParsers:
    """Cover the tool parsers the original suite never touched."""

    def test_copilot_nested_integrations(self, tmp_path: Path):
        path = tmp_path / "apps.json"
        path.write_text(
            json.dumps({
                "integrations": {
                    "vscode": {
                        "mcpServers": {
                            "github": {"command": "npx", "args": ["-y", "pkg@v1.2.0"]},
                            "broken": {"args": ["-y", "pkg"]},
                        }
                    }
                }
            })
        )
        servers = parse_copilot_json(path)
        assert [s.name for s in servers] == ["github"]
        assert servers[0].tool == ToolName.COPILOT
        assert servers[0].version == "v1.2.0"

    def test_vscode_settings_key(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"mcp.servers": {"linear": {"command": "npx", "args": ["-y", "linear-mcp@v3"]}}})
        )
        servers = parse_vscode_json(path)
        assert len(servers) == 1
        assert servers[0].tool == ToolName.VSCODE
        assert servers[0].version == "v3"

    def test_windsurf_config(self, tmp_path: Path):
        path = tmp_path / "mcp_config.json"
        path.write_text(json.dumps({"mcpServers": {"plain": "npx -y plain-mcp"}}))
        servers = parse_windsurf_json(path)
        assert len(servers) == 1
        assert servers[0].command == "npx -y plain-mcp"
        assert servers[0].tool == ToolName.WINDSURF

    @pytest.mark.parametrize(
        "parser",
        [parse_copilot_json, parse_vscode_json, parse_windsurf_json],
    )
    def test_malformed_json_returns_empty(self, parser, tmp_path: Path):
        path = tmp_path / "broken.json"
        path.write_text("{not json")
        assert parser(path) == []

    @pytest.mark.parametrize(
        "parser",
        [parse_copilot_json, parse_vscode_json, parse_windsurf_json],
    )
    def test_missing_file_returns_empty(self, parser, tmp_path: Path):
        assert parser(tmp_path / "absent.json") == []

    @pytest.mark.parametrize(
        "parser",
        [parse_claude_json, parse_cursor_json],
    )
    def test_claude_and_cursor_malformed_json_returns_empty(self, parser, tmp_path: Path):
        path = tmp_path / "broken.json"
        path.write_text("{not json")
        assert parser(path) == []

    def test_codex_without_toml_support_returns_empty(self, tmp_path: Path, monkeypatch):
        """On Python < 3.11 without tomli, the parser degrades to no servers."""
        path = tmp_path / "config.toml"
        path.write_text("[mcp_servers.github]\ncommand = \"npx\"\n")
        monkeypatch.setattr("mcp_reconcile.tools.codex.tomllib", None)
        assert parse_codex_toml(path) == []

    def test_codex_malformed_toml_returns_empty(self, tmp_path: Path):
        path = tmp_path / "config.toml"
        path.write_text("this is not = = toml [[[")
        assert parse_codex_toml(path) == []


class TestMCPServerModelEdges:
    """Cover the model branches the original suite left out."""

    def test_to_dict_round_trip(self):
        server = _server(
            "github",
            ToolName.CLAUDE,
            args=("-y", "pkg@v1"),
            env=(("B", "2"), ("A", "1")),
        )
        data = server.to_dict()
        assert data["args"] == ["-y", "pkg@v1"]
        assert data["env"] == {"A": "1", "B": "2"}
        assert data["tool"] == "claude"
        assert data["source"] == ""

    def test_version_ignores_untagged_args(self):
        server = _server("x", ToolName.CLAUDE, args=("-y", "--registry", "http://reg"))
        assert server.version is None

    def test_scan_result_queries(self):
        result = ScanResult(
            servers=[
                _server("github", ToolName.CLAUDE),
                _server("github", ToolName.CURSOR),
                _server("linear", ToolName.CLAUDE),
            ]
        )
        assert result.server_count == 3
        assert result.tool_count == 2
        assert len(result.by_tool(ToolName.CLAUDE)) == 2
        assert len(result.by_name("github")) == 2
        assert result.has_drift is False

    def test_drift_to_dict_without_canonical(self):
        drift = Drift(server_name="x", drift_type=DriftType.ORPHAN, description="d")
        data = drift.to_dict()
        assert data["canonical"] is None
        assert data["drifts"] == []
