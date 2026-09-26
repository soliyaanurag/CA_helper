"""Flask extension objects.

They are created once here, without an app, and bound to the app inside
`create_app()` (the "app factory" pattern). Import them from here, e.g.
`from app.extensions import db`.
"""

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.errors import CaHelperApi

# Deterministic names for indexes and constraints, so Alembic migrations
# generated on different machines are identical and can be downgraded.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base behind `db.Model`. Models subclass BaseModel (app/models/base.py)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# SQLAlchemy 2.x style: models subclass db.Model, which uses our Base.
db = SQLAlchemy(model_class=Base)
migrate = Migrate()

# flask-smorest Api: blueprints, marshmallow schemas, OpenAPI spec, Swagger UI,
# and our JSON error format (see app/errors.py).
api = CaHelperApi()

jwt = JWTManager()
cors = CORS()
# No global limit. Individual routes (login, OTP) add @limiter.limit(...).
limiter = Limiter(key_func=get_remote_address)
