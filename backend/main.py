"""Run the API with Flask's development server (debugger and auto-reload).

    make dev-backend
    # or by hand:  conda activate ca-helper && cd backend && python main.py

Serves http://127.0.0.1:8000 and needs `make infra` for the database.
This file is main.py, not app.py: an app.py here would shadow the `app` package.
"""

import os

from app import create_app

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    app = create_app()  # config from APP_ENV in the root .env (development)
    # With auto-reload the script runs twice (a watcher and the server); print once.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        base = f"http://{HOST}:{PORT}"
        print(f"API:     {base}/api/v1/...")
        print(f"Swagger: {base}/api/docs")
        print(f"Health:  {base}/api/health")
    app.run(host=HOST, port=PORT, debug=True)


if __name__ == "__main__":
    main()
