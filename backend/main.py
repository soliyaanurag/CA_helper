"""Run the API by hand with Flask's development server.

    conda activate ca-helper
    cd backend
    python main.py

Same app as every other entrypoint (create_app()); only the server differs:
this uses Flask's dev server on 127.0.0.1:8000, with the debugger and auto-reload
when the config says so (DEV_SERVER_DEBUG, on in development). Needs `make infra`
for the database. Not used by Docker (gunicorn) or the Makefile (`flask run`).

This file is main.py, not app.py: an app.py here would shadow the `app` package.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

HOST = "127.0.0.1"
PORT = 8000

# The shared root .env (one level above backend/). Variables already set win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app import create_app  # noqa: E402  (after load_dotenv, so APP_ENV is known)


def build_app(config_name: str | None = None) -> Flask:
    """The app, configured from APP_ENV (tests pass "testing")."""
    return create_app(config_name)


def main() -> None:
    app = build_app()
    # With auto-reload the script runs twice (a watcher and the server); print once.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        base = f"http://{HOST}:{PORT}"
        print(f"API:     {base}/api/v1/...")
        print(f"Swagger: {base}/api/docs")
        print(f"Health:  {base}/api/health")
    debug = app.config["DEV_SERVER_DEBUG"]
    app.run(host=HOST, port=PORT, debug=debug, use_reloader=debug)


if __name__ == "__main__":
    main()
