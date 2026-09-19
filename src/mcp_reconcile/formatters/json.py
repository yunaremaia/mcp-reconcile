"""JSON formatter for drift output."""
from __future__ import annotations

import json

from .models import ScanResult


def format_scan_result(result: ScanResult) -> str:
    """Format scan results as JSON."""
    data = {
        "servers": [s.to_dict() for s in result.servers],
        "drifts": [d.to_dict() for d in result.drifts],
        "summary": {
            "total_servers": result.server_count,
            "total_tools": result.tool_count,
            "drift_count": len(result.drifts),
            "has_drift": result.has_drift,
        },
        "errors": result.errors,
    }
    return json.dumps(data, indent=2)
