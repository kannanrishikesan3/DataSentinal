"""Report generation: JSON, CSV, HTML, and a plain-text summary (spec
section 29). Every format is built from the same intermediate `ReportData`
so the three stay consistent with each other.
"""

from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from pathlib import PurePath

from datasentinel_agent.reporting.recommendations import recommend_for_file
from datasentinel_agent.storage.models import FindingORM, ScanRecord


def build_report_data(scan: ScanRecord, findings: list[FindingORM]) -> dict:
    severity_counts = Counter(f.severity for f in findings)
    category_counts = Counter(f.category for f in findings)
    affected_endpoints = sorted({f.endpoint_id for f in findings if f.endpoint_id})
    affected_directories = sorted({str(PurePath(f.file_path).parent) for f in findings})

    by_file: dict[str, list[FindingORM]] = {}
    for f in findings:
        by_file.setdefault(f.file_path, []).append(f)

    recommendations: list[dict] = []
    for file_path, file_findings in by_file.items():
        worst = max(file_findings, key=lambda f: {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}[f.severity])
        categories = {f.category for f in file_findings if not f.is_secret}
        has_secret = any(f.is_secret for f in file_findings)
        for advice in recommend_for_file(categories, has_secret, worst.severity):
            recommendations.append({"file_path": file_path, "severity": worst.severity, "recommendation": advice})

    return {
        "scan_id": scan.scan_id,
        "profile": scan.profile,
        "status": scan.status,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "scan_paths": scan.scan_paths,
        "files_discovered": scan.files_discovered,
        "files_scanned": scan.files_scanned,
        "files_skipped": scan.files_skipped,
        "pii_findings": scan.pii_findings,
        "secret_findings": scan.secret_findings,
        "severity_distribution": dict(severity_counts),
        "category_distribution": dict(category_counts),
        "affected_endpoints": affected_endpoints,
        "affected_directories": affected_directories,
        "findings": [
            {
                "finding_id": f.finding_id,
                "file_path": f.file_path,
                "category": f.category,
                "is_secret": f.is_secret,
                "severity": f.severity,
                "confidence": f.confidence,
                "occurrence_count": f.occurrence_count,
                "detection_method": f.detection_method,
                "redacted_evidence": f.redacted_evidence,
                "status": f.status,
                "detected_at": f.detected_at.isoformat() if f.detected_at else None,
            }
            for f in findings
        ],
        "recommendations": recommendations,
    }


def render_text(data: dict) -> str:
    lines = [
        "DataSentinel Scan Report",
        "=" * 25,
        f"Scan ID: {data['scan_id']}",
        f"Profile: {data['profile']}   Status: {data['status']}",
        f"Started: {data['started_at']}   Completed: {data['completed_at']}",
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

    lines.append("")
    lines.append("Categories found:")
    for category, count in sorted(data["category_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {category}: {count:,}")

    if data["affected_endpoints"]:
        lines.append("")
        lines.append(f"Affected endpoints: {', '.join(data['affected_endpoints'])}")

    lines.append("")
    lines.append(f"Affected directories ({len(data['affected_directories'])}):")
    for directory in data["affected_directories"][:20]:
        lines.append(f"  {directory}")
    if len(data["affected_directories"]) > 20:
        lines.append(f"  ... and {len(data['affected_directories']) - 20} more")

    if data["recommendations"]:
        lines.append("")
        lines.append("Recommendations:")
        for rec in data["recommendations"][:20]:
            lines.append(f"  [{rec['severity'].upper()}] {rec['file_path']}: {rec['recommendation']}")

    return "\n".join(lines)


def render_json(data: dict) -> str:
    return json.dumps(data, indent=2, default=str)


def render_csv(data: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["finding_id", "file_path", "category", "is_secret", "severity", "confidence", "occurrence_count", "detection_method", "redacted_evidence", "status", "detected_at"]
    )
    for f in data["findings"]:
        writer.writerow(
            [f["finding_id"], f["file_path"], f["category"], f["is_secret"], f["severity"], f["confidence"], f["occurrence_count"], f["detection_method"], f["redacted_evidence"], f["status"], f["detected_at"]]
        )
    return buffer.getvalue()


_SEVERITY_COLORS = {
    "critical": "#dc2626", "high": "#ea580c", "medium": "#ca8a04", "low": "#2563eb", "informational": "#64748b",
}  # fmt: skip


def render_html(data: dict) -> str:
    def esc(value) -> str:
        return html.escape(str(value))

    severity_rows = "".join(
        f"<tr><td>{esc(sev.capitalize())}</td><td style='color:{_SEVERITY_COLORS[sev]}'>{esc(data['severity_distribution'].get(sev, 0))}</td></tr>"
        for sev in ("critical", "high", "medium", "low", "informational")
    )
    finding_rows = "".join(
        f"<tr><td>{esc(f['severity'])}</td><td>{esc(f['category'])}</td><td>{esc(f['file_path'])}</td>"
        f"<td>{esc(f['redacted_evidence'])}</td><td>{esc(f['confidence'])}</td><td>{esc(f['occurrence_count'])}</td></tr>"
        for f in data["findings"]
    )
    recommendation_items = "".join(
        f"<li><strong>[{esc(rec['severity'].upper())}]</strong> {esc(rec['file_path'])}: {esc(rec['recommendation'])}</li>"
        for rec in data["recommendations"]
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>DataSentinel Scan Report {esc(data['scan_id'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
th {{ background: #f4f4f5; }}
h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
</style></head>
<body>
<h1>DataSentinel Scan Report</h1>
<p>Scan ID: {esc(data['scan_id'])} &mdash; Profile: {esc(data['profile'])} &mdash; Status: {esc(data['status'])}</p>
<p>Files discovered: {esc(data['files_discovered'])} | scanned: {esc(data['files_scanned'])} | skipped: {esc(data['files_skipped'])}</p>
<h2>Severity distribution</h2>
<table><tr><th>Severity</th><th>Count</th></tr>{severity_rows}</table>
<h2>Findings</h2>
<table><tr><th>Severity</th><th>Category</th><th>File</th><th>Evidence</th><th>Confidence</th><th>Occurrences</th></tr>{finding_rows}</table>
<h2>Recommendations</h2>
<ul>{recommendation_items}</ul>
</body></html>"""


_RENDERERS = {"text": render_text, "json": render_json, "csv": render_csv, "html": render_html}


def generate_report(scan: ScanRecord, findings: list[FindingORM], output_format: str = "text") -> str:
    if output_format not in _RENDERERS:
        raise ValueError(f"Unsupported report format: {output_format}")
    data = build_report_data(scan, findings)
    return _RENDERERS[output_format](data)
