"""Background worker: runs scheduled jobs (reminders, scrapers, expiry checks).

It runs as its OWN process, never inside the web server:
    hybrid mode:  make dev-worker
    Docker:       the `worker` service in docker-compose.yml

Every job is added in build_scheduler() below and calls a service function. Jobs
run inside the Flask app context, so they use db.session and services exactly
like routes do. APScheduler logs each job's start, finish or failure by name.

Health: the built-in `worker.heartbeat` job touches HEARTBEAT_FILE every 30 seconds.
`python worker.py --healthcheck` (the Docker healthcheck) exits 1 if that file is
older than 90 seconds, i.e. the scheduler has stopped running jobs.
"""

import functools
import logging
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask

from app import create_app

log = logging.getLogger("worker")

# Cron times in register_jobs() are written in Indian time (e.g. hour=8 is 08:00 IST).
# Data is still stored in UTC.
SCHEDULER_TIMEZONE = "Asia/Kolkata"

HEARTBEAT_FILE = Path(tempfile.gettempdir()) / "ca-helper-worker.heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_MAX_AGE_SECONDS = 90
HEARTBEAT_JOB_ID = "worker.heartbeat"


class AppScheduler(BlockingScheduler):
    """APScheduler BlockingScheduler that runs every job inside the Flask app context."""

    def __init__(self, app: Flask, **kwargs):
        super().__init__(timezone=SCHEDULER_TIMEZONE, **kwargs)
        self.app = app

    def add_job(self, func, *args, **kwargs):
        @functools.wraps(func)  # keeps the function's name for APScheduler's log lines
        def run_in_app_context(*job_args, **job_kwargs):
            with self.app.app_context():
                return func(*job_args, **job_kwargs)

        return super().add_job(run_in_app_context, *args, **kwargs)


def write_heartbeat() -> None:
    """Record that the scheduler is alive (read by `--healthcheck`)."""
    HEARTBEAT_FILE.write_text(datetime.now(UTC).isoformat())


def heartbeat_is_fresh(max_age_seconds: float = HEARTBEAT_MAX_AGE_SECONDS) -> bool:
    """True if the heartbeat file was written within the last `max_age_seconds`."""
    try:
        age = time.time() - HEARTBEAT_FILE.stat().st_mtime
    except FileNotFoundError:
        return False
    return age <= max_age_seconds


def build_scheduler(app: Flask) -> AppScheduler:
    """Create the scheduler with every job."""
    scheduler = AppScheduler(app)
    scheduler.add_job(
        write_heartbeat,
        "interval",
        seconds=HEARTBEAT_INTERVAL_SECONDS,
        id=HEARTBEAT_JOB_ID,
        next_run_time=datetime.now(UTC),  # first beat immediately at start
    )
    # Feature jobs go here, each calling a service function. Cron times are IST, e.g.
    #   scheduler.add_job(alerts_service.send_reminders, "cron", hour=8, id="alerts.reminders")
    return scheduler


def main() -> None:
    app = create_app()  # also configures logging (LOG_LEVEL)
    scheduler = build_scheduler(app)
    job_ids = [job.id for job in scheduler.get_jobs()]
    log.info("Worker starting with %d job(s): %s", len(job_ids), ", ".join(job_ids))
    try:
        scheduler.start()  # blocks until Ctrl+C / container stop
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped")


if __name__ == "__main__":
    if sys.argv[1:] == ["--healthcheck"]:
        sys.exit(0 if heartbeat_is_fresh() else 1)
    main()
