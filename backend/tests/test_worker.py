"""worker.py: jobs run in the app context, and the heartbeat healthcheck."""

import os
import threading
import time

import pytest
from flask import current_app

import worker
from worker import HEARTBEAT_JOB_ID, AppScheduler, build_scheduler


def test_only_the_heartbeat_job_is_registered_yet(app):
    scheduler = build_scheduler(app)

    assert [job.id for job in scheduler.get_jobs()] == [HEARTBEAT_JOB_ID]


def test_jobs_run_inside_app_context(app):
    scheduler = AppScheduler(app)
    job = scheduler.add_job(lambda: current_app.name, "interval", hours=1, id="test.app_name")

    # APScheduler runs jobs in worker threads, which start with no app context.
    result = {}
    thread = threading.Thread(target=lambda: result.update(name=job.func()))
    thread.start()
    thread.join()

    assert result["name"] == app.name


@pytest.fixture()
def heartbeat_file(tmp_path, monkeypatch):
    path = tmp_path / "worker.heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", path)
    return path


def test_healthcheck_fails_without_a_heartbeat(heartbeat_file):
    assert worker.heartbeat_is_fresh() is False


def test_heartbeat_job_makes_the_healthcheck_pass(heartbeat_file):
    worker.write_heartbeat()

    assert worker.heartbeat_is_fresh() is True


def test_healthcheck_fails_on_a_stale_heartbeat(heartbeat_file):
    worker.write_heartbeat()
    stale = time.time() - worker.HEARTBEAT_MAX_AGE_SECONDS - 1
    os.utime(heartbeat_file, (stale, stale))

    assert worker.heartbeat_is_fresh() is False
