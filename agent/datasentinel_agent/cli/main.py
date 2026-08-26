"""The `datasentinel` command-line entry point."""

from __future__ import annotations

from pathlib import Path

import click

from datasentinel_agent import __version__
from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.config.settings import get_settings
from datasentinel_agent.core.enums import Severity
from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.discovery.config import resolve_default_include_paths
from datasentinel_agent.pii import presidio_engine
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory, session_scope
from datasentinel_agent.storage.repository import get_scan, list_findings, list_scans

PRODUCT_NAME = "DataSentinel"
TAGLINE = "Endpoint Data Risk Discovery"

_DISPLAY_SEVERITIES = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFORMATIONAL]


def _banner() -> None:
    click.echo(f"{PRODUCT_NAME}\n{TAGLINE}\n")


def _get_session_factory():
    settings = get_settings()
    engine = make_engine(settings.db_path)
    init_db(engine)
    return make_session_factory(engine)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name=PRODUCT_NAME)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """DataSentinel — Discover. Classify. Protect."""
    if ctx.invoked_subcommand is None:
        _banner()
        click.echo(ctx.get_help())


@cli.command()
@click.option("--path", "paths", multiple=True, type=click.Path(path_type=Path), help="Path to scan. Repeatable.")
@click.option(
    "--profile", type=click.Choice(["quick", "standard", "deep", "custom"]), default=None, help="Scan profile."
)
@click.option("--no-ai", is_flag=True, default=False, help="Disable OpenRouter classification for this scan.")
def scan(paths: tuple[Path, ...], profile: str | None, no_ai: bool) -> None:
    """Scan the given path(s) (or the OS default locations) for PII and secrets."""
    settings = get_settings()
    resolved_paths = list(paths) if paths else resolve_default_include_paths()

    if not resolved_paths:
        raise click.ClickException(
            "No scan paths given and no default include paths exist on this system. Pass --path."
        )

    _banner()
    click.echo("Scanning:")
    for p in resolved_paths:
        click.echo(str(p))
    click.echo()

    options = ScanOptions(
        profile=profile,
        paths=resolved_paths,
        use_ai=settings.ai_configured and not no_ai,
        use_presidio=presidio_engine.is_available(),
    )

    session_factory = _get_session_factory()
    with click.progressbar(length=0, label="Scanning", show_pos=True) as bar:
        def on_progress(name: str, data: dict) -> None:
            if name == "discovery_completed":
                bar.length = data["files_discovered"]
            elif name == "file_scanned":
                bar.update(1)

        summary = run_scan(options, session_factory, on_progress=on_progress)

    click.echo(f"\nScan ID: {summary.scan_id}")
    click.echo(f"Status: {summary.status.value}\n")
    click.echo(f"Files discovered: {summary.files_discovered:,}")
    click.echo(f"Files scanned: {summary.files_scanned:,}")
    click.echo(f"Files skipped: {summary.files_skipped:,}\n")
    click.echo(f"PII findings: {summary.pii_findings:,}")
    click.echo(f"Secrets: {summary.secret_findings:,}\n")
    for severity in _DISPLAY_SEVERITIES:
        click.echo(f"{severity.value.capitalize()}: {summary.severity_counts.get(severity, 0):,}")


def _write_env_credentials(env_file: Path, server_url: str, api_token: str) -> None:
    """Merges DATASENTINEL_BACKEND_URL/DATASENTINEL_ENDPOINT_TOKEN into
    `env_file`, preserving any other lines already there (AI settings, log
    level, ...) rather than clobbering the whole file."""
    keys_to_replace = {"DATASENTINEL_BACKEND_URL", "DATASENTINEL_ENDPOINT_TOKEN"}
    existing_lines: list[str] = []
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else None
            if key not in keys_to_replace:
                existing_lines.append(line)

    existing_lines.append(f"DATASENTINEL_BACKEND_URL={server_url}")
    existing_lines.append(f"DATASENTINEL_ENDPOINT_TOKEN={api_token}")
    env_file.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


@cli.command()
@click.option("--server-url", required=True, help="The DataSentinel backend's base URL.")
@click.option("--token", "enrollment_token", required=True, help="Reusable enrollment token from the dashboard.")
@click.option("--name", default=None, help="Display name for this endpoint. Defaults to this machine's hostname.")
@click.option("--hostname", default=None, help="Defaults to this machine's real hostname.")
@click.option("--os", "os_name", type=click.Choice(["windows", "linux", "macos"]), default=None, help="Defaults to auto-detected.")
@click.option(
    "--env-file", type=click.Path(path_type=Path), default=Path(".env"),
    help="Where to write DATASENTINEL_BACKEND_URL/DATASENTINEL_ENDPOINT_TOKEN once enrolled.",
)
def enroll(
    server_url: str, enrollment_token: str, name: str | None, hostname: str | None,
    os_name: str | None, env_file: Path,
) -> None:
    """Self-register this machine using a reusable enrollment token (spec
    sections 7-13) — the counterpart to an admin manually registering an
    endpoint from the dashboard. The enrollment token itself is never
    written anywhere; only the resulting per-endpoint credential is."""
    import socket

    import httpx

    from datasentinel_agent.core.platform import detect_platform

    resolved_hostname = hostname or socket.gethostname()
    resolved_name = name or resolved_hostname
    resolved_os = os_name or detect_platform().value

    _banner()
    click.echo(f"Enrolling '{resolved_hostname}' ({resolved_os}) with {server_url} ...\n")

    try:
        response = httpx.post(
            f"{server_url.rstrip('/')}/api/v1/endpoints/enroll",
            json={
                "enrollment_token": enrollment_token,
                "name": resolved_name,
                "hostname": resolved_hostname,
                "os": resolved_os,
                "agent_version": __version__,
            },
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:  # noqa: BLE001 - a non-JSON error body must not crash the CLI
            detail = exc.response.text
        raise click.ClickException(f"Enrollment rejected ({exc.response.status_code}): {detail}")
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Could not reach {server_url}: {exc}")

    body = response.json()
    _write_env_credentials(env_file, server_url, body["api_token"])

    click.echo(click.style("[OK] ", fg="green") + f"Enrolled as endpoint {body['endpoint']['id']}")
    click.echo(f"     Credentials written to {env_file.resolve()}")
    click.echo("     Run 'datasentinel scan' or start the service to begin scanning.")


@cli.command()
def status() -> None:
    """Show agent configuration and the most recent scan."""
    settings = get_settings()
    _banner()

    click.echo(f"Local database: {settings.db_path}")
    click.echo(f"AI enabled: {settings.ai_enabled} (configured: {settings.ai_configured})")
    click.echo(f"Presidio available: {presidio_engine.is_available()}\n")

    session_factory = _get_session_factory()
    with session_scope(session_factory) as session:
        scans = list_scans(session, limit=1)
        if not scans:
            click.echo("No scans have been run yet.")
            return
        latest = scans[0]
        click.echo(f"Last scan: {latest.scan_id}")
        click.echo(f"  Profile: {latest.profile}")
        click.echo(f"  Status: {latest.status}")
        click.echo(f"  Started: {latest.started_at}")
        click.echo(f"  Files scanned: {latest.files_scanned:,}")
        click.echo(f"  PII findings: {latest.pii_findings:,}")
        click.echo(f"  Secrets: {latest.secret_findings:,}")


@cli.command()
@click.option("--scan-id", required=True, help="Scan ID to report on.")
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json", "csv", "html"]), default="text"
)
@click.option("--output", type=click.Path(path_type=Path), default=None, help="Write to a file instead of stdout.")
def report(scan_id: str, output_format: str, output: Path | None) -> None:
    """Generate a report for a completed scan."""
    from datasentinel_agent.reporting.generator import generate_report

    session_factory = _get_session_factory()
    with session_scope(session_factory) as session:
        scan_record = get_scan(session, scan_id)
        if scan_record is None:
            raise click.ClickException(f"No scan found with ID {scan_id}")
        findings = list_findings(session, scan_id=scan_id, limit=100_000)
        content = generate_report(scan_record, findings, output_format)

    if output:
        output.write_text(content, encoding="utf-8")
        click.echo(f"Report written to {output}")
    else:
        click.echo(content)


@cli.group("config")
def config_group() -> None:
    """Configuration utilities."""


@config_group.command("validate")
def config_validate() -> None:
    """Validate settings and the scan configuration."""
    _banner()
    ok = True

    try:
        settings = get_settings()
        click.echo(click.style("[OK] ", fg="green") + "Environment settings loaded")
        click.echo(f"     AI enabled: {settings.ai_enabled}, configured: {settings.ai_configured}")
    except Exception as exc:
        ok = False
        click.echo(click.style("[FAIL] ", fg="red") + f"Environment settings: {exc}")

    try:
        scan_config = load_scan_config()
        click.echo(click.style("[OK] ", fg="green") + "Scan configuration loaded")
        click.echo(f"     Profiles: {', '.join(sorted(scan_config.scan.profiles))}")
    except Exception as exc:
        ok = False
        click.echo(click.style("[FAIL] ", fg="red") + f"Scan configuration: {exc}")

    presidio_status = "available" if presidio_engine.is_available() else "unavailable (regex-only detection)"
    click.echo(click.style("[OK] ", fg="green") + f"Presidio: {presidio_status}")

    if not ok:
        raise click.exceptions.Exit(1)


@cli.group("schedule")
def schedule_group() -> None:
    """Manage recurring/one-time scan schedules."""


@schedule_group.command("add")
@click.option("--name", required=True)
@click.option("--type", "schedule_type", required=True, type=click.Choice(["once", "daily", "weekly", "custom"]))
@click.option("--profile", default="standard", type=click.Choice(["quick", "standard", "deep", "custom"]))
@click.option("--path", "paths", multiple=True, type=click.Path(path_type=Path))
@click.option("--run-at", default=None, help="ISO datetime, required for --type once.")
@click.option("--time", "time_of_day", default=None, help="HH:MM (24h), required for daily/weekly.")
@click.option("--day-of-week", default=None, type=click.IntRange(0, 6), help="0=Monday..6=Sunday, required for weekly.")
@click.option("--interval-seconds", default=None, type=int, help="Required for --type custom.")
def schedule_add(
    name: str,
    schedule_type: str,
    profile: str,
    paths: tuple[Path, ...],
    run_at: str | None,
    time_of_day: str | None,
    day_of_week: int | None,
    interval_seconds: int | None,
) -> None:
    """Add a new scan schedule."""
    from datetime import datetime
    from uuid import uuid4

    from datasentinel_agent.scheduler import ScheduleConfig, upsert_schedule

    try:
        schedule = ScheduleConfig(
            id=str(uuid4()),
            name=name,
            schedule_type=schedule_type,  # type: ignore[arg-type]
            scan_profile=profile,
            scan_paths=[str(p) for p in paths] or None,
            run_at=datetime.fromisoformat(run_at) if run_at else None,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            interval_seconds=interval_seconds,
        )
    except Exception as exc:
        raise click.ClickException(str(exc))

    upsert_schedule(schedule)
    click.echo(f"Schedule '{name}' created (id: {schedule.id})")


@schedule_group.command("list")
def schedule_list() -> None:
    """List configured schedules."""
    from datasentinel_agent.scheduler import load_schedules

    schedules = load_schedules()
    if not schedules:
        click.echo("No schedules configured.")
        return
    for schedule in schedules:
        status = "enabled" if schedule.enabled else "disabled"
        click.echo(f"{schedule.name}  [{schedule.id[:8]}]  {schedule.schedule_type}  {status}  next_run={schedule.next_run_at}")


@schedule_group.command("remove")
@click.argument("schedule_id")
def schedule_remove(schedule_id: str) -> None:
    """Remove a schedule by ID."""
    from datasentinel_agent.scheduler import remove_schedule

    if remove_schedule(schedule_id):
        click.echo(f"Removed schedule {schedule_id}")
    else:
        raise click.ClickException(f"No schedule found with ID {schedule_id}")


@schedule_group.command("run")
@click.option("--once", is_flag=True, help="Run a single check cycle and exit, instead of running forever.")
def schedule_run(once: bool) -> None:
    """Run the scheduler loop in the foreground (used by the Windows Service / systemd unit)."""
    import signal

    from datasentinel_agent.scheduler import SchedulerService

    scan_config = load_scan_config()
    session_factory = _get_session_factory()

    def on_event(name: str, data: dict) -> None:
        click.echo(f"[{name}] {data}")

    service = SchedulerService(
        session_factory,
        max_cpu_percent=scan_config.scan.max_cpu_percent,
        on_event=on_event,
    )

    if once:
        service.tick()
        return

    # systemd sends SIGTERM (not SIGINT) on stop/restart; Python only turns
    # SIGINT into KeyboardInterrupt by default, so SIGTERM needs an explicit
    # handler or `systemctl stop` would hang until the unit's timeout kills
    # the process instead of shutting down cleanly.
    def _handle_shutdown_signal(signum, _frame) -> None:
        click.echo(f"Received signal {signum}, shutting down gracefully…")
        service.stop()

    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    service.run_forever()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
