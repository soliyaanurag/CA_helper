"""Background worker: runs scheduled jobs (reminders, scrapers, expiry checks).

It runs as its OWN process, never inside the web server:
    hybrid mode:  make dev-worker
    Docker:       the `worker` service in docker-compose.yml

Each feature module may define `register_jobs(scheduler)` in its __init__.py.
This file collects them all. Every job runs inside the Flask app context, so
jobs use db.session and service functions exactly like routes do.

Example, in app/modules/alerts/__init__.py:

    def register_jobs(scheduler):
        scheduler.add_job(send_due_reminders, "cron", hour=8, id="alerts.due_reminders")
"""

import functools
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask

from app import create_app
from app.modules import register_all_jobs

log = logging.getLogger("worker")

# Cron times in register_jobs() are written in Indian time (e.g. hour=8 is 08:00 IST).
# Data is still stored in UTC.
SCHEDULER_TIMEZONE = "Asia/Kolkata"


class AppScheduler(BlockingScheduler):
    """APScheduler BlockingScheduler that runs every job inside the Flask app context."""

    def __init__(self, app: Flask, **kwargs):
        super().__init__(timezone=SCHEDULER_TIMEZONE, **kwargs)
        self.app = app

    def add_job(self, func, *args, **kwargs):
        @functools.wraps(func)
        def run_in_app_context(*job_args, **job_kwargs):
            with self.app.app_context():
                return func(*job_args, **job_kwargs)

        return super().add_job(run_in_app_context, *args, **kwargs)


def build_scheduler(app: Flask) -> AppScheduler:
    """Create the scheduler and let every module register its jobs."""
    scheduler = AppScheduler(app)
    modules = register_all_jobs(scheduler)
    log.info("Modules with jobs: %s", ", ".join(modules) or "(none)")
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = create_app()
    scheduler = build_scheduler(app)
    job_ids = [job.id for job in scheduler.get_jobs()]
    log.info("Worker starting with %d job(s): %s", len(job_ids), ", ".join(job_ids) or "(none)")
    try:
        scheduler.start()  # blocks until Ctrl+C / container stop
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped")


if __name__ == "__main__":
    main()
