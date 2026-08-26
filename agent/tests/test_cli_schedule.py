"""Phase 15 tests: `datasentinel schedule` CLI commands."""

from click.testing import CliRunner

from datasentinel_agent.cli.main import cli


def _run(runner, args, tmp_path, extra_env=None):
    env = {"DATASENTINEL_DB_PATH": str(tmp_path / "ds.db"), "DATASENTINEL_SCHEDULES_PATH": str(tmp_path / "schedules.json")}
    if extra_env:
        env.update(extra_env)
    return runner.invoke(cli, args, env=env)


def test_schedule_add_and_list(tmp_path):
    runner = CliRunner()
    add_result = _run(
        runner,
        ["schedule", "add", "--name", "nightly", "--type", "daily", "--time", "02:00"],
        tmp_path,
    )
    assert add_result.exit_code == 0, add_result.output
    assert "created" in add_result.output

    list_result = _run(runner, ["schedule", "list"], tmp_path)
    assert list_result.exit_code == 0
    assert "nightly" in list_result.output


def test_schedule_add_rejects_missing_required_fields(tmp_path):
    runner = CliRunner()
    result = _run(runner, ["schedule", "add", "--name", "bad", "--type", "weekly"], tmp_path)
    assert result.exit_code != 0


def test_schedule_remove(tmp_path):
    runner = CliRunner()
    _run(runner, ["schedule", "add", "--name", "temp", "--type", "custom", "--interval-seconds", "60"], tmp_path)

    from datasentinel_agent.scheduler.store import load_schedules

    schedules_path = tmp_path / "schedules.json"
    schedule_id = load_schedules(schedules_path)[0].id

    remove_result = _run(runner, ["schedule", "remove", schedule_id], tmp_path)
    assert remove_result.exit_code == 0
    assert load_schedules(schedules_path) == []


def test_schedule_list_empty(tmp_path):
    runner = CliRunner()
    result = _run(runner, ["schedule", "list"], tmp_path)
    assert result.exit_code == 0
    assert "No schedules configured." in result.output


def test_schedule_run_once_executes_due_schedule(tmp_path):
    from datetime import datetime, timedelta, timezone

    scan_dir = tmp_path / "target"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("Email: cli.schedule@example.com\n")

    from datasentinel_agent.scheduler.models import ScheduleConfig, ScheduleType
    from datasentinel_agent.scheduler.store import save_schedules

    schedules_path = tmp_path / "schedules.json"
    schedule = ScheduleConfig(
        id="due", name="due-now", schedule_type=ScheduleType.CUSTOM, interval_seconds=60,
        scan_paths=[str(scan_dir)],
    )
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    save_schedules([schedule], schedules_path)

    runner = CliRunner()
    result = _run(runner, ["schedule", "run", "--once"], tmp_path)
    assert result.exit_code == 0, result.output
    assert "scan_triggered" in result.output
