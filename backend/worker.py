"""Background worker: runs scheduled jobs (reminders, scrapers, expiry checks).

It runs as its OWN process, never inside the web server: `make dev-worker`.

Every job is added in build_scheduler() below and calls a service function. Jobs
run inside the Flask app context, so they use db.session and services exactly
like routes do. APScheduler logs each job's start, finish or failure by name.
"""

import functools
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask

from app import create_app

log = logging.getLogger("worker")

# Cron times in build_scheduler() are written in Indian time (e.g. hour=8 is 08:00 IST).
# Data is still stored in UTC.
SCHEDULER_TIMEZONE = "Asia/Kolkata"


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


def build_scheduler(app: Flask) -> AppScheduler:
    """Create the scheduler with every job."""
    scheduler = AppScheduler(app)
    # Feature jobs go here, each calling a service function. Cron times are IST, e.g.
    #   scheduler.add_job(alerts_service.send_reminders, "cron", hour=8, id="alerts.reminders")
    return scheduler


def main() -> None:
    app = create_app()  # also configures logging (LOG_LEVEL)
    scheduler = build_scheduler(app)
    job_ids = [job.id for job in scheduler.get_jobs()]
    log.info("Worker starting with %d job(s): %s", len(job_ids), ", ".join(job_ids))
    try:
        scheduler.start()  # blocks until Ctrl+C
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped")


if __name__ == "__main__":
    main()
