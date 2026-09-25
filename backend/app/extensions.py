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

from app.core.db.base import Base
from app.core.errors import CaHelperApi

# SQLAlchemy 2.x style: models subclass db.Model, which uses our Base
# (with deterministic constraint names for Alembic).
db = SQLAlchemy(model_class=Base)
migrate = Migrate()

# flask-smorest Api: blueprints, marshmallow schemas, OpenAPI spec, Swagger UI,
# and our JSON error format (see app/core/errors.py).
api = CaHelperApi()

jwt = JWTManager()
cors = CORS()
# No global limit. Individual routes (login, OTP) add @limiter.limit(...) later.
limiter = Limiter(key_func=get_remote_address)
