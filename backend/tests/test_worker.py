"""worker.py: jobs run inside the Flask app context."""

import threading

from flask import current_app

from worker import AppScheduler


def test_jobs_run_inside_app_context(app):
    scheduler = AppScheduler(app)
    job = scheduler.add_job(lambda: current_app.name, "interval", hours=1, id="test.app_name")

    # APScheduler runs jobs in worker threads, which start with no app context.
    result = {}
    thread = threading.Thread(target=lambda: result.update(name=job.func()))
    thread.start()
    thread.join()

    assert result["name"] == app.name
