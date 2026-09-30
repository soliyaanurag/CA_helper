"""The background worker: runs the 4 scheduled jobs in their own process.

    docker compose --profile worker up     (only ONE teammate runs it)

Each job runs inside the Flask app context, so it uses the database like a route does.
Cron times are Indian time (hour=8 is 08:00 IST); data is still stored in UTC.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app import alerts, compliance, create_app, marketplace, regulatory

log = logging.getLogger("worker")


def run_job(app, job):
    """Run one job inside the Flask app context."""
    with app.app_context():
        job()


def build_scheduler(app) -> BlockingScheduler:
    """The scheduler with every job."""
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    # Every hour, late filings the business has not started become "overdue" (hourly, so
    # a worker started late in the day catches up soon).
    scheduler.add_job(
        run_job, "interval", hours=1, args=[app, compliance.mark_overdue_filings],
        id="compliance.mark_overdue", name="compliance.mark_overdue",
    )
    # Every 15 minutes, requests a CA did not answer within 48 hours expire.
    scheduler.add_job(
        run_job, "interval", minutes=15, args=[app, marketplace.expire_old_requests],
        id="marketplace.expire_requests", name="marketplace.expire_requests",
    )
    # Every morning at 08:15 (after the overdue job): T-7 / T-3 / T-1 and overdue reminders.
    scheduler.add_job(
        run_job, "cron", hour=8, minute=15, args=[app, alerts.send_reminders],
        id="alerts.reminders", name="alerts.reminders",
    )
    # Every morning at 07:00: read the news sources and tell users about rule changes.
    scheduler.add_job(
        run_job, "cron", hour=7, minute=0, args=[app, regulatory.scan_news],
        id="regulatory.scan_news", name="regulatory.scan_news",
    )
    return scheduler


def main() -> None:
    app = create_app()  # also sets up logging (LOG_LEVEL)
    scheduler = build_scheduler(app)
    job_ids = [job.id for job in scheduler.get_jobs()]
    log.info("Worker starting with %d job(s): %s", len(job_ids), ", ".join(job_ids))
    try:
        scheduler.start()  # blocks until Ctrl+C
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped")


if __name__ == "__main__":
    main()
