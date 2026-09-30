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

from app import alerts, compliance, create_app, marketplace, regulatory

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
    #   scheduler.add_job(<module>_service.send_digest, "cron", hour=8, id="<module>.digest")

    # CO11: every hour, late filings the business has not started become "overdue".
    # Hourly (not once at midnight), so a worker started late in the day catches up soon.
    scheduler.add_job(
        compliance.mark_overdue_filings,
        "interval",
        hours=1,
        id="compliance.mark_overdue",
    )

    # MA12: every 15 minutes, requests unanswered for 48 hours expire.
    scheduler.add_job(
        marketplace.expire_old_requests,
        "interval",
        minutes=15,
        id="marketplace.expire_requests",
    )

    # AL2: every morning, deadline (T-7/T-3/T-1) and overdue reminders, by tray and email.
    # 08:15, after the hourly overdue job has had a chance to run.
    scheduler.add_job(
        alerts.send_reminders, "cron", hour=8, minute=15, id="alerts.reminders"
    )

    # RE2 (X2): every morning, read the news sources and save changes for an admin to review.
    scheduler.add_job(
        regulatory.scan_news, "cron", hour=7, minute=0, id="regulatory.scan_news"
    )
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
