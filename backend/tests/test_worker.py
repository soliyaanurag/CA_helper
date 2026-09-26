"""worker.py: module jobs are collected and every job runs inside the app context."""

import threading

from flask import current_app

from worker import AppScheduler, build_scheduler


def test_no_module_registers_jobs_yet(app):
    scheduler = build_scheduler(app)

    assert scheduler.get_jobs() == []


def test_jobs_run_inside_app_context(app):
    scheduler = AppScheduler(app)
    job = scheduler.add_job(lambda: current_app.name, "interval", hours=1, id="test.app_name")

    # APScheduler runs jobs in worker threads, which start with no app context.
    result = {}
    thread = threading.Thread(target=lambda: result.update(name=job.func()))
    thread.start()
    thread.join()

    assert result["name"] == app.name
