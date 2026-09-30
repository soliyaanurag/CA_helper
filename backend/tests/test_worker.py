"""worker.py: jobs run inside the Flask app context."""

import threading

from flask import current_app

from worker import build_scheduler, run_job


def test_jobs_run_inside_app_context(app):
    # APScheduler runs jobs in worker threads, which start with no app context.
    result = {}
    thread = threading.Thread(
        target=run_job, args=[app, lambda: result.update(name=current_app.name)]
    )
    thread.start()
    thread.join()

    assert result["name"] == app.name


def test_the_worker_has_its_four_jobs(app):
    jobs = {job.id: str(job.trigger) for job in build_scheduler(app).get_jobs()}

    assert jobs == {
        "compliance.mark_overdue": "interval[1:00:00]",
        "marketplace.expire_requests": "interval[0:15:00]",
        "alerts.reminders": "cron[hour='8', minute='15']",
        "regulatory.scan_news": "cron[hour='7', minute='0']",
    }
