"""worker.py: module jobs, app context, job names in logs, and the heartbeat healthcheck."""

import io
import logging
import os
import threading
import time

import pytest
from flask import current_app

import worker
from app.core.logging_config import TEXT_FORMAT, ContextFilter
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


def test_log_lines_inside_a_job_carry_the_job_name(app):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(logging.Formatter(TEXT_FORMAT))
    logging.getLogger().addHandler(handler)
    scheduler = AppScheduler(app)
    job = scheduler.add_job(
        lambda: logging.getLogger("app.test").info("working"), "interval", hours=1, id="demo.job"
    )
    try:
        job.func()
        logging.getLogger("app.test").info("after the job")
    finally:
        logging.getLogger().removeHandler(handler)

    lines = stream.getvalue().splitlines()
    assert any("job=demo.job working" in line for line in lines)
    assert any("job=demo.job Job finished in" in line for line in lines)
    assert lines[-1].endswith("job=- after the job")


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
