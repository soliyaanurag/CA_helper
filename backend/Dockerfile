# Backend image, used by two services in docker-compose.yml:
#   backend: default command below (migrations, then gunicorn via gunicorn.conf.py)
#   worker:  overrides the command with `python worker.py`
# Dependencies come from requirements.txt, the same file the conda env uses.

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_APP=app

# Tesseract for local OCR (documents never leave our server).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user; /data/uploads is the uploads volume.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/uploads \
    && chown -R app:app /data
USER app

EXPOSE 8000
# gunicorn reads gunicorn.conf.py (bind, workers, logging) from the working directory.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn 'app:create_app()'"]
