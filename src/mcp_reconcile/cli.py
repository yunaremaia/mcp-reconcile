"""CLI for mcp-reconcile."""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import reconcile, scanner
from .formatters.json import format_scan_result as format_json
from .formatters.text import format_scan_result as format_text


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mcp-reconcile",
        description="Cross-tool MCP configuration drift detection and reconciliation",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for drift")
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    # Fix command
    fix_parser = subparsers.add_parser("fix", help="Fix detected drift")
    fix_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )
    fix_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to config files",
    )

    args = parser.parse_args(argv)

    if args.command == "scan":
        return _cmd_scan(args)
    elif args.command == "fix":
        return _cmd_fix(args)
    else:
        parser.print_help()
        return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    """Handle the scan command."""
    result = scanner.scan_all()
    result.drifts = reconcile.detect_drift(result)

    if args.json:
        print(format_json(result))
    else:
        print(format_text(result))

    # Return 1 on drift (CI-friendly)
    return 1 if result.has_drift else 0


def _cmd_fix(args: argparse.Namespace) -> int:
    """Handle the fix command."""
    result = scanner.scan_all()
    result.drifts = reconcile.detect_drift(result)

    if not result.drifts:
        print("No drift to fix.")
        return 0

    plan = reconcile.generate_fix_plan(result.drifts)

    if args.dry_run:
        print(f"Would execute {len(plan)} fix operation(s):")
        for op in plan:
            print(f"  {op['action']}: {op.get('tool', '?')} {op['server']} -> {op.get('to', op.get('from', '?'))}")
        return 0

    if args.apply:
        # TODO: Implement actual fix application
        print(f"Applying {len(plan)} fix operation(s)...")
        for op in plan:
            print(f"  APPLY: {op}")
        return 0

    print(f"Detected {len(plan)} operation(s). Use --dry-run to preview or --apply to execute.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
