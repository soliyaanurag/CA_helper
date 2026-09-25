"""backend/main.py (manual dev server) builds the app without starting a server."""

import importlib

from flask import Flask


def test_main_builds_the_app_without_running_it(monkeypatch):
    started = []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: started.append(kwargs))
    main = importlib.import_module("main")  # importing must not start anything

    app = main.build_app("testing")

    assert started == []
    assert "/api/v1/auth/login" in {rule.rule for rule in app.url_map.iter_rules()}


def test_main_runs_the_dev_server_on_localhost_8000(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: started.append(kwargs))
    main = importlib.import_module("main")
    monkeypatch.setattr(main, "build_app", lambda: main.create_app("testing"))

    main.main()

    assert started == [{"host": "127.0.0.1", "port": 8000, "debug": False, "use_reloader": False}]
    assert "http://127.0.0.1:8000/api/docs" in capsys.readouterr().out
