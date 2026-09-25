"""GET /api/health: is the API up and can it reach the database?

Used by the Docker healthcheck, CI and the frontend's status badge.
"""

import logging

from flask_smorest import Blueprint
from marshmallow import Schema, fields
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

log = logging.getLogger(__name__)

blp = Blueprint("health", __name__, url_prefix="/api", description="Service health check")


class HealthSchema(Schema):
    status = fields.String(required=True, metadata={"description": "ok | degraded"})
    database = fields.String(required=True, metadata={"description": "ok | unavailable"})


@blp.route("/health")
@blp.doc(security=[])  # public: no token needed
@blp.response(200, HealthSchema)
@blp.alt_response(503, schema=HealthSchema, description="The database is unreachable")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        log.warning("Health check: database unavailable", exc_info=True)
        db.session.rollback()
        database = "unavailable"

    if database == "ok":
        return {"status": "ok", "database": database}
    return {"status": "degraded", "database": database}, 503
