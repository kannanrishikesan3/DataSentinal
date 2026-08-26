"""Report generation for a centrally stored scan (spec section 29): scan
summary, files scanned/skipped, PII categories, severity distribution,
secrets, affected directories, recommendations. Mirrors the agent's own
local report shape independently — see the note in `api/v1/reports.py`.
"""

from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from pathlib import PurePath

from datasentinel_backend.models.models import Finding, Scan, ScanError

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}

_RECOMMENDATION_DEFAULT = "Review this file's sensitivity and restrict access or relocate it to approved storage as appropriate."
_RECOMMENDATION_SECRET = (
    "Rotate this credential immediately and remove it from the file. Store secrets in a "
    "managed secrets vault, never in endpoint storage."
)


def _build_data(scan: Scan, findings: list[Finding], errors: list[ScanError]) -> dict:
    severity_counts = Counter(f.severity for f in findings)
    category_counts = Counter(f.category for f in findings)
    affected_directories = sorted({str(PurePath(f.file_path).parent) for f in findings})

    by_file: dict[str, list[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.file_path, []).append(f)

    recommendations = []
    for file_path, file_findings in by_file.items():
        worst = max(file_findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 0))
        has_secret = any(f.is_secret for f in file_findings)
        advice = _RECOMMENDATION_SECRET if has_secret else _RECOMMENDATION_DEFAULT
        recommendations.append({"file_path": file_path, "severity": worst.severity, "recommendation": advice})

    return {
        "scan_id": str(scan.id),
        "endpoint_id": str(scan.endpoint_id),
        "profile": scan.profile,
        "status": scan.status,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "files_discovered": scan.files_discovered,
        "files_scanned": scan.files_scanned,
        "files_skipped": scan.files_skipped,
        "pii_findings": scan.pii_findings,
        "secret_findings": scan.secret_findings,
        "severity_distribution": dict(severity_counts),
        "category_distribution": dict(category_counts),
        "affected_directories": affected_directories,
        "findings": [
            {
                "finding_id": str(f.id), "file_path": f.file_path, "category": f.category,
                "is_secret": f.is_secret, "severity": f.severity, "confidence": f.confidence,
                "occurrence_count": f.occurrence_count, "detection_method": f.detection_method,
                "redacted_evidence": f.redacted_evidence, "status": f.status,
                "detected_at": f.detected_at.isoformat() if f.detected_at else None,
            }
            for f in findings
        ],
        "recommendations": recommendations,
        "errors": [
            {
                "path": e.path,
                "error_type": e.error_type,
                "message": e.message,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in errors
        ],
    }


def _render_text(data: dict) -> str:
    lines = [
        "DataSentinel Scan Report", "=" * 25,
        f"Scan ID: {data['scan_id']}   Endpoint: {data['endpoint_id']}",
        f"Profile: {data['profile']}   Status: {data['status']}",
        "",
        f"Files discovered: {data['files_discovered']:,}",
        f"Files scanned:    {data['files_scanned']:,}",
        f"Files skipped:    {data['files_skipped']:,}",
        "",
        f"PII findings: {data['pii_findings']:,}",
        f"Secrets:      {data['secret_findings']:,}",
        "",
        "Severity distribution:",
    ]
    for severity in ("critical", "high", "medium", "low", "informational"):
        lines.append(f"  {severity.capitalize()}: {data['severity_distribution'].get(severity, 0):,}")

    lines += ["", f"Errors ({len(data['errors']):,}):"]
    if data["errors"]:
        for error in data["errors"]:
            lines.append(f"  [{error['error_type']}] {error['path']}: {error['message']}")
    else:
        lines.append("  None")
    return "\n".join(lines)


def _render_json(data: dict) -> str:
    return json.dumps(data, indent=2, default=str)


def _render_csv(data: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["finding_id", "file_path", "category", "is_secret", "severity", "confidence", "occurrence_count", "detection_method", "redacted_evidence", "status"])
    for f in data["findings"]:
        writer.writerow([f["finding_id"], f["file_path"], f["category"], f["is_secret"], f["severity"], f["confidence"], f["occurrence_count"], f["detection_method"], f["redacted_evidence"], f["status"]])

    writer.writerow([])
    writer.writerow(["Errors"])
    writer.writerow(["path", "error_type", "message", "occurred_at"])
    for e in data["errors"]:
        writer.writerow([e["path"], e["error_type"], e["message"], e["occurred_at"]])
    return buffer.getvalue()


def _render_html(data: dict) -> str:
    def esc(v) -> str:
        return html.escape(str(v))

    rows = "".join(
        f"<tr><td>{esc(f['severity'])}</td><td>{esc(f['category'])}</td><td>{esc(f['file_path'])}</td><td>{esc(f['redacted_evidence'])}</td></tr>"
        for f in data["findings"]
    )
    error_rows = "".join(
        f"<tr><td>{esc(e['path'])}</td><td>{esc(e['error_type'])}</td><td>{esc(e['message'])}</td></tr>"
        for e in data["errors"]
    )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Scan Report {esc(data['scan_id'])}</title></head>"
        f"<body><h1>DataSentinel Scan Report</h1><p>Scan {esc(data['scan_id'])} — {esc(data['status'])}</p>"
        f"<table border='1'><tr><th>Severity</th><th>Category</th><th>File</th><th>Evidence</th></tr>{rows}</table>"
        f"<h2>Errors</h2><table border='1'><tr><th>Path</th><th>Type</th><th>Message</th></tr>{error_rows}</table>"
        "</body></html>"
    )


_RENDERERS = {"text": _render_text, "json": _render_json, "csv": _render_csv, "html": _render_html}


def generate_backend_report(scan: Scan, findings: list[Finding], errors: list[ScanError], output_format: str) -> str:
    return _RENDERERS[output_format](_build_data(scan, findings, errors))
