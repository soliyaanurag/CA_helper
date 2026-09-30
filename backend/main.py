"""Run the API with Flask's development server (debugger and auto-reload).

    docker compose up   (the backend service runs `python main.py`)

Serves port 8000 on every interface, so the browser and the frontend container can reach it.
This file is main.py, not app.py: an app.py here would shadow the `app` package.
"""

import os

from app import create_app

HOST = "0.0.0.0"
PORT = 8000


def main() -> None:
    app = create_app()
    # With auto-reload the script runs twice (a watcher and the server); print once.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        base = f"http://localhost:{PORT}"
        print(f"API:     {base}/api/v1/...")
        print(f"Health:  {base}/api/health")
    app.run(host=HOST, port=PORT, debug=True)


if __name__ == "__main__":
    main()
