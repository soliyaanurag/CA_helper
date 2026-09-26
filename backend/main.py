"""Run the API by hand with Flask's development server.

    conda activate ca-helper
    cd backend
    python main.py

Same app as every other entrypoint (create_app()); this uses Flask's dev server on
127.0.0.1:8000, with the debugger and auto-reload in development (DEV_SERVER_DEBUG).
Needs `make infra` for the database. The Makefile uses `flask run` instead.

This file is main.py, not app.py: an app.py here would shadow the `app` package.
"""

import os

from app import create_app  # also loads the root .env (app/config.py)

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    app = create_app()
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
