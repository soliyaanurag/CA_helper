"""Feature modules and their auto-discovery.

Every sub-package of `app.modules` is a feature module (onboarding, compliance,
...). There is no central list to edit: creating the package is enough.

A module's `__init__.py` exposes:

    blp            flask-smorest Blueprint (required), registered on the API under
                   API_PREFIX (/api/v1); the blueprint itself sets no url_prefix
    seed()         optional; inserts dev seed data (idempotent), run by `flask seed`
                   after the core seeds (demo users, app/core/auth/seed.py)
    SEED_ORDER     optional int, default 100; lower numbers are seeded first
    register_jobs(scheduler)
                   optional; adds scheduled jobs; called ONLY by worker.py

See docs/PATTERNS.md for how to add routes, jobs and seeds.
"""

import importlib
import pkgutil
from types import ModuleType

DEFAULT_SEED_ORDER = 100
# Every module route lives under this prefix (docs/API_CONVENTIONS.md).
# Core infra endpoints (/api/health, /api/docs, /api/openapi.json) stay unversioned.
API_PREFIX = "/api/v1"


def discover_modules() -> list[ModuleType]:
    """Import and return every feature module package, sorted by name."""
    found = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if info.ispkg:
            found.append(importlib.import_module(f"{__name__}.{info.name}"))
    return found


def module_name(module: ModuleType) -> str:
    """Short name of a module package, e.g. "onboarding"."""
    return module.__name__.rsplit(".", 1)[-1]


def register_blueprints(api) -> None:
    """Register every module's `blp` on the flask-smorest Api, under API_PREFIX."""
    for module in discover_modules():
        blp = getattr(module, "blp", None)
        if blp is None:
            raise RuntimeError(f"{module.__name__} must expose a flask-smorest Blueprint `blp`")
        api.register_blueprint(blp, url_prefix=API_PREFIX)


def register_all_jobs(scheduler) -> list[str]:
    """Call `register_jobs(scheduler)` on each module that defines it (worker only)."""
    registered = []
    for module in discover_modules():
        register_jobs = getattr(module, "register_jobs", None)
        if register_jobs is not None:
            register_jobs(scheduler)
            registered.append(module_name(module))
    return registered


def run_all_seeds() -> list[str]:
    """Run the core seeds, then each module's `seed()` in SEED_ORDER, then commit once.

    Seeding is one unit of work: a seed() adds rows but does not commit.
    Core seeds (demo users) run first because modules' seed data may refer to users.
    """
    from app.core.auth.seed import seed as seed_users
    from app.extensions import db

    # Core seeds (not auto-discovered): add new ones here, in dependency order.
    core_seeds = [("core.auth", seed_users)]
    for _, core_seed in core_seeds:
        core_seed()
    modules = [m for m in discover_modules() if getattr(m, "seed", None) is not None]
    modules.sort(key=lambda m: (getattr(m, "SEED_ORDER", DEFAULT_SEED_ORDER), module_name(m)))
    for module in modules:
        module.seed()
    db.session.commit()
    return [name for name, _ in core_seeds] + [module_name(m) for m in modules]
