"""Phase 9 tests: the full CLI, exercised end-to-end against a real temp
directory and a temp SQLite DB (no mocking of the pipeline)."""

import os

from click.testing import CliRunner

from datasentinel_agent.cli.main import cli


def _run(runner, args, db_path):
    return runner.invoke(cli, args, env={"DATASENTINEL_DB_PATH": str(db_path)})


def test_version_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "DataSentinel" in result.output


def test_no_args_shows_banner_and_help():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "DataSentinel" in result.output
    assert "Endpoint Data Risk Discovery" in result.output


def test_config_validate_succeeds_with_default_config(tmp_path):
    runner = CliRunner()
    result = _run(runner, ["config", "validate"], tmp_path / "ds.db")
    assert result.exit_code == 0
    assert "Environment settings loaded" in result.output
    assert "Scan configuration loaded" in result.output


def test_scan_reports_findings_for_a_real_directory(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("Email: cli.test@example.com\n")

    runner = CliRunner()
    result = _run(runner, ["scan", "--path", str(scan_dir), "--no-ai"], tmp_path / "ds.db")

    assert result.exit_code == 0, result.output
    assert "DataSentinel" in result.output
    assert "Files discovered: 1" in result.output
    assert "PII findings:" in result.output
    assert "Critical:" in result.output


def test_status_reports_no_scans_before_any_run(tmp_path):
    runner = CliRunner()
    result = _run(runner, ["status"], tmp_path / "fresh.db")
    assert result.exit_code == 0
    assert "No scans have been run yet." in result.output


def test_status_reports_last_scan_after_a_run(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("nothing sensitive\n")
    db_path = tmp_path / "ds.db"

    runner = CliRunner()
    _run(runner, ["scan", "--path", str(scan_dir)], db_path)
    result = _run(runner, ["status"], db_path)

    assert result.exit_code == 0
    assert "Last scan:" in result.output


def test_report_unknown_scan_id_fails_cleanly(tmp_path):
    runner = CliRunner()
    result = _run(runner, ["report", "--scan-id", "does-not-exist"], tmp_path / "ds.db")
    assert result.exit_code != 0
    assert "No scan found" in result.output


def test_report_after_scan_produces_json(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("Email: report.test@example.com\n")
    db_path = tmp_path / "ds.db"

    runner = CliRunner()
    scan_result = _run(runner, ["scan", "--path", str(scan_dir)], db_path)
    scan_id = next(line.split(": ", 1)[1] for line in scan_result.output.splitlines() if line.startswith("Scan ID:"))

    report_result = _run(runner, ["report", "--scan-id", scan_id, "--format", "json"], db_path)
    assert report_result.exit_code == 0
    assert scan_id in report_result.output
