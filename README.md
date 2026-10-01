# MCP Reconcile

![CI](https://github.com/yunaremaia/mcp-reconcile/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9-blue.svg)
![License](https://img.shields.io/github/license/yunaremaia/mcp-reconcile)


**Cross-tool MCP configuration drift detection and reconcile.**

You use Claude Code, Cursor, Copilot, Codex, and Windsurf. Each has its own MCP config format and location. When you add a server in one, it doesn't appear in others. When you update a version or arg in one, others remain stale. `mcp-reconcile` detects that drift — and can fix it.

## The Problem

```
~/.claude.json          -> { mcpServers: { github: { command: "npx", args: ["-y", "@modelcontextprotocol/server-github@v1.2.0"] }}}
~/.cursor/mcp.json      -> { mcpServers: { github: { command: "npx", args: ["-y", "@modelcontextprotocol/server-github@v1.1.0"] }}}
~/.codex/config.toml    -> [mcp_servers.github] command = "npx" args = ["-y", "@modelcontextprotocol/server-github@v1.0.0"]
```

Same server. Three versions. Zero warnings. Your agents behave differently depending on which tool you open. Production bugs follow.

## The Solution

```bash
$ mcp-reconcile scan
DRIFT: github server version differs across tools
  Claude Code  -> @modelcontextprotocol/server-github@v1.2.0
  Cursor       -> @modelcontextprotocol/server-github@v1.1.0  (STALE)
  Codex        -> @modelcontextprotocol/server-github@v1.0.0  (STALE)

DRIFT: filesystem server missing from Cursor and Codex

DRIFT: brave-search server present only in Cursor (not in other tools)

Summary: 3 servers across 3 tools, 2 drifts detected, 1 missing, 1 orphan
```

```bash
$ mcp-reconcile fix --dry-run
Would update Cursor: github v1.1.0 -> v1.2.0
Would update Codex:  github v1.0.0 -> v1.2.0
Would add filesystem server to Cursor and Codex

$ mcp-reconcile fix --apply
Updated Cursor: github v1.1.0 -> v1.2.0
Updated Codex:  github v1.0.0 -> v1.2.0
Added filesystem server to Cursor and Codex
```

## Supported Tools

| Tool | Config Path | Format |
|------|-------------|--------|
| Claude Code | `~/.claude.json` | JSON |
| Claude Code (project) | `.mcp.json` | JSON |
| Cursor | `~/.cursor/mcp.json` | JSON |
| Cursor (project) | `.cursor/mcp.json` | JSON |
| Copilot | `~/.config/github-copilot/apps.json` | JSON |
| Codex | `~/.codex/config.toml` | TOML |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | JSON |
| VS Code | `.vscode/settings.json` | JSON |

## Installation

```bash
pip install mcp-reconcile
```

Or from source:

```bash
git clone https://github.com/yunaremaia/mcp-reconcile.git
cd mcp-reconcile
pip install -e .
```

## Usage

### Scan for drift

```bash
mcp-reconcile scan
```

Exit code 1 on drift (CI-friendly).

### Fix drift

```bash
mcp-reconcile fix --dry-run   # preview changes
mcp-reconcile fix --apply     # write changes
```

### CI integration

```yaml
- name: Check MCP config drift
  run: mcp-reconcile scan
```

### JSON output

```bash
mcp-reconcile scan --json
```

## What It Detects

- **Version drift**: Same server, different version tags across tools
- **Arg drift**: Same server, different arguments (env vars, flags)
- **Missing server**: Server configured in some tools but not others
- **Orphan server**: Server in one tool, absent everywhere else (possible dead config)
- **Command drift**: Same server, different launcher commands (npx vs uvx vs python)

## Roadmap

- [ ] Lockfile mode: declare canonical MCP config, enforce across tools
- [ ] Auto-sync: watch for changes and reconcile automatically
- [ ] MCP Registry integration: pull latest versions from registry
- [ ] Diff rendering: side-by-side config comparison
- [ ] Selective sync: choose which tools to include/exclude
- [ ] Server health check: verify each server starts after reconcile
- [ ] SARIF output: integrate with code scanning dashboards

## Architecture

```
mcp-reconcile/
├── mcp_reconcile/
│   ├── __init__.py
│   ├── cli.py              # entry point
│   ├── scanner.py          # reads all tool configs
│   ├── models.py           # Server, ToolConfig, Drift types
│   ├── reconcile.py        # diff + fix logic
│   ├── tools/
│   │   ├── claude.py       # Claude Code config parser
│   │   ├── cursor.py       # Cursor config parser
│   │   ├── copilot.py      # Copilot config parser
│   │   ├── codex.py        # Codex config parser
│   │   ├── windsurf.py     # Windsurf config parser
│   │   └── vscode.py       # VS Code config parser
│   └── formatters/
│       ├── text.py         # human-readable output
│       └── json.py         # JSON output
├── tests/
├── pyproject.toml
└── README.md
```


If this tool is useful to you, a star helps other people find it.

## Related tools

- **[mcp-guard](https://github.com/yunaremaia/mcp-guard)** — audit MCP servers for unsafe permissions
- **[context-bridge](https://github.com/yunaremaia/context-bridge)** — persistent session memory for AI agents
- **[tool-call-retry](https://github.com/yunaremaia/tool-call-retry)** — retry failed tool calls with backoff
- **[agent-guard](https://github.com/yunaremaia/agent-guard)** — enforce guardrails on AI agent tool calls

Part of a family of focused, single-purpose developer tools — each one does one thing
and does it well.

## License

MIT

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
