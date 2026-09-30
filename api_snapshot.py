"""Temporary safety net for the simplification (deleted at the end).

Builds a fresh database, runs `seed-demo`, logs in as the demo business, CA and admin,
calls every GET endpoint and records the JSON *structure* (keys and value types, not values).

    python api_snapshot.py            write api_snapshot_baseline.json
    python api_snapshot.py --compare  print the differences from the baseline

Run it from the repo root on the host (conda env) or in the backend container
(`docker compose exec backend python ../api_snapshot.py`). It uses the database server in
DATABASE_URL, but its own database `ca_helper_snapshot`, which it drops and recreates.
"""

import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "api_snapshot_baseline.json"
CURRENT = ROOT / "api_snapshot_current.json"
MAX_DETAIL_CALLS = 40  # detail endpoints are called for up to this many ids each


def load_env():
    """Read the root .env into os.environ without overriding what is already set."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def fresh_database():
    """Drop and create the snapshot database; point DATABASE_URL at it."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"]).set(database="ca_helper_snapshot")
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS ca_helper_snapshot WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE ca_helper_snapshot"))
    server.dispose()
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)


# ---------- structure of a JSON value ----------

MONEY = re.compile(r"^-?\d+\.\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if MONEY.match(value):
        return "money"
    if DATETIME.match(value):
        return "datetime"
    if DATE.match(value):
        return "date"
    if UUID.match(value):
        return "uuid"
    return "string"


def collect(value, path, shape):
    """Add path -> type for value and everything inside it to shape (a dict of sets)."""
    shape.setdefault(path, set()).add(type_name(value))
    if isinstance(value, dict):
        for key, child in value.items():
            collect(child, f"{path}.{key}", shape)
    elif isinstance(value, list):
        for child in value:
            collect(child, f"{path}[]", shape)


# ---------- calling the API ----------


class Recorder:
    def __init__(self, client):
        self.client = client
        self.results = {}  # "role GET /path" -> {"status": set, "type": set, "shape": dict}
        self.called_rules = set()

    def get(self, role, token, url, name=None, rule=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = self.client.get(url, headers=headers)
        entry = self.results.setdefault(
            f"{role} GET {name or url}", {"status": set(), "type": set(), "shape": {}}
        )
        entry["status"].add(response.status_code)
        entry["type"].add(response.mimetype)
        if rule:
            self.called_rules.add(rule)
        if response.is_json:
            collect(response.get_json(), "$", entry["shape"])
            return response.get_json()
        return None

    def record_post(self, role, url, body, data):
        entry = self.results.setdefault(
            f"{role} POST {url}", {"status": set(), "type": set(), "shape": {}}
        )
        entry["status"].add(200)
        entry["type"].add("application/json")
        collect(data, "$", entry["shape"])


def ids_in(data, key="id"):
    """The `key` values of the rows of a list response ({items: [...]} or a plain list)."""
    rows = data.get("items") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return [row[key] for row in rows if isinstance(row, dict) and row.get(key)]


def snapshot():
    load_env()
    os.environ["APP_ENV"] = "development"
    os.environ["GEMINI_API_KEY"] = ""  # no network calls; AI features use their fallback
    os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="snapshot-uploads-")
    fresh_database()
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT / "backend")

    from sqlalchemy import text

    from app import create_app

    app = create_app()
    db = app.extensions["sqlalchemy"]
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.create_all()
        result = app.test_cli_runner().invoke(args=["seed-demo"])
        if result.exit_code != 0:
            raise SystemExit(f"seed-demo failed:\n{result.output}\n{result.exception!r}")

    client = app.test_client()
    rec = Recorder(client)
    tokens = {}
    for role in ("business", "ca", "admin"):
        body = {
            "email": os.environ[f"DEMO_{role.upper()}_EMAIL"],
            "password": os.environ[f"DEMO_{role.upper()}_PASSWORD"],
        }
        response = client.post("/api/v1/auth/login", json=body)
        if response.status_code != 200:
            raise SystemExit(f"login as {role} failed: {response.status_code} {response.data!r}")
        tokens[role] = response.get_json()["access_token"]
        rec.record_post(role, "/api/v1/auth/login", body, response.get_json())

    get_rules = sorted(
        rule.rule
        for rule in app.url_map.iter_rules()
        if "GET" in rule.methods and rule.rule.startswith("/api/") and rule.rule != "/api/openapi.json"
        and not rule.rule.startswith("/api/docs")
    )

    # 1. Every GET endpoint without path parameters, as each role and without a token.
    for rule in get_rules:
        if "<" in rule:
            continue
        for role in ("business", "ca", "admin", "anonymous"):
            rec.get(role, tokens.get(role), rule, rule=rule)

    # 2. List endpoints with the filters the frontend sends.
    B, C, A = tokens["business"], tokens["ca"], tokens["admin"]
    items = rec.get("business", B, "/api/v1/compliance/items")
    item_ids = ids_in(items)
    item_rows = items if isinstance(items, list) else items.get("items", [])
    fy = next((row.get("financial_year") for row in item_rows if row.get("financial_year")), "2026-27")
    for query in ("status=overdue", "status=filed_verified", "status=upcoming", "form_code=gstr_3b",
                  "form_code=itr", "due_from=2026-10-01&due_to=2026-12-31", "status=bogus"):
        rec.get("business", B, f"/api/v1/compliance/items?{query}")
    for query in (f"fy={fy}", "doc_type=acknowledgement", "page_size=5"):
        rec.get("business", B, f"/api/v1/documents?{query}")
    for item_id in item_ids[:MAX_DETAIL_CALLS]:
        rec.get("business", B, f"/api/v1/documents?compliance_item_id={item_id}",
                name="/api/v1/documents?compliance_item_id=<id>")
    rec.get("business", B, "/api/v1/alerts/notifications?page_size=5")
    for query in ("service=gstr_3b", "specialization=itr", "language=hindi", "city=Mumbai", "page=2",
                  "service=gstr_3b&city=Mumbai&language=english&specialization=gstr_1"):
        rec.get("business", B, f"/api/v1/marketplace/cas?{query}")
    rec.get("business", B, "/api/v1/onboarding/nic-codes?q=retail")
    rec.get("business", B, "/api/v1/onboarding/nic-codes?q=software")
    for query in ("role=business", "role=ca", "search=demo", "page=2"):
        rec.get("admin", A, f"/api/v1/admin/users?{query}")
    for status in ("pending", "verified", "rejected"):
        rec.get("admin", A, f"/api/v1/admin/cas?status={status}")
    for status in ("pending", "approved", "rejected", "all"):
        rec.get("admin", A, f"/api/v1/admin/regulatory/changes?status={status}")
    rec.get("admin", A, "/api/v1/admin/audit-log?page=1")

    # 3. Endpoints with ids, the ids taken from the list responses.
    def each(role, token, rule, ids, **extra):
        for value in ids[:MAX_DETAIL_CALLS]:
            url = re.sub(r"<[^>]*item_id>|<[^>]*ca_id>|<[^>]*business_id>|<[^>]*document_id>|"
                         r"<[^>]*form_code>", lambda m: str(value), rule)
            rec.get(role, token, url + extra.get("query", ""), name=rule + extra.get("query", ""), rule=rule)

    for rule in ("/api/v1/compliance/items/<uuid:item_id>",
                 "/api/v1/compliance/items/<uuid:item_id>/peer-insights",
                 "/api/v1/compliance/items/<uuid:item_id>/acknowledgement",
                 "/api/v1/alerts/penalties/<uuid:item_id>"):
        each("business", B, rule, item_ids)
    each("business", B, "/api/v1/alerts/penalties/<uuid:item_id>", item_ids, query="?tax_due=25000")
    for item_id in item_ids[:MAX_DETAIL_CALLS]:
        rec.get("business", B, f"/api/v1/ca-workspace/document-requests?compliance_item_id={item_id}",
                name="/api/v1/ca-workspace/document-requests?compliance_item_id=<id>")

    form_codes = sorted({row["form_code"] for row in item_rows if row.get("form_code")})
    each("business", B, "/api/v1/compliance/forms/<string:form_code>", form_codes)
    each("business", B, "/api/v1/compliance/forms/<string:form_code>", ["no_such_form"])

    documents = rec.get("business", B, "/api/v1/documents?page_size=100")
    each("business", B, "/api/v1/documents/<uuid:document_id>/file", ids_in(documents))

    cas = rec.get("business", B, "/api/v1/marketplace/cas?page_size=100")
    ca_ids = ids_in(cas)
    each("business", B, "/api/v1/marketplace/cas/<uuid:ca_id>", ca_ids)
    each("business", B, "/api/v1/marketplace/cas/<uuid:ca_id>/requestable-filings", ca_ids)

    clients = rec.get("ca", C, "/api/v1/ca-workspace/clients")
    client_ids = ids_in(clients, "business_id") or ids_in(clients)
    each("ca", C, "/api/v1/ca-workspace/clients/<uuid:business_id>", client_ids)
    # A CA opening the documents of its clients (allowed for active engagements only).
    for business_id in client_ids[:MAX_DETAIL_CALLS]:
        page = rec.get("ca", C, f"/api/v1/ca-workspace/clients/{business_id}", name="(ids for CA files)")
        doc_ids = set()
        walk_ids(page, "document_id", doc_ids)
        for document_id in sorted(doc_ids):
            rec.get("ca", C, f"/api/v1/documents/{document_id}/file",
                    name="/api/v1/documents/<uuid:document_id>/file", rule="/api/v1/documents/<uuid:document_id>/file")

    admin_cas = []
    for status in ("pending", "verified", "rejected"):
        admin_cas += ids_in(rec.get("admin", A, f"/api/v1/admin/cas?status={status}"))
    each("admin", A, "/api/v1/admin/cas/<uuid:ca_id>", admin_cas)
    each("admin", A, "/api/v1/admin/cas/<uuid:ca_id>/certificate", admin_cas)

    # 4. Error shapes: an unknown id, and another business's filing.
    missing = str(uuid.uuid4())
    rec.get("business", B, f"/api/v1/compliance/items/{missing}", name="/api/v1/compliance/items/<missing>")
    rec.get("ca", C, f"/api/v1/ca-workspace/clients/{missing}", name="/api/v1/ca-workspace/clients/<missing>")
    rec.get("business", B, f"/api/v1/marketplace/cas/{missing}", name="/api/v1/marketplace/cas/<missing>")
    rec.get("admin", A, f"/api/v1/admin/cas/{missing}", name="/api/v1/admin/cas/<missing>")
    rec.get("business", B, f"/api/v1/documents/{missing}/file", name="/api/v1/documents/<missing>/file")

    not_called = [rule for rule in get_rules if "<" in rule and rule not in rec.called_rules]
    return {
        "endpoints": {
            key: {
                "status": sorted(entry["status"]),
                "type": sorted(t or "" for t in entry["type"]),
                "shape": {path: "|".join(sorted(types)) for path, types in sorted(entry["shape"].items())},
            }
            for key, entry in sorted(rec.results.items())
            if not key.endswith("(ids for CA files)")
        },
        "get_rules": get_rules,
        "rules_not_called": not_called,
    }


def walk_ids(value, key, found):
    """Every value of `key` anywhere inside value."""
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key and isinstance(child, str):
                found.add(child)
            walk_ids(child, key, found)
    elif isinstance(value, list):
        for child in value:
            walk_ids(child, key, found)


def compare(old, new):
    lines = []
    for rule in sorted(set(old["get_rules"]) | set(new["get_rules"])):
        if rule not in new["get_rules"]:
            lines.append(f"GET route removed: {rule}")
        elif rule not in old["get_rules"]:
            lines.append(f"GET route added: {rule}")
    for rule in new["rules_not_called"]:
        lines.append(f"GET route with ids never called (add it to the script): {rule}")
    old_e, new_e = old["endpoints"], new["endpoints"]
    for key in sorted(set(old_e) | set(new_e)):
        if key not in new_e:
            lines.append(f"- {key}: no longer called")
            continue
        if key not in old_e:
            lines.append(f"+ {key}: new, status {new_e[key]['status']}")
            continue
        a, b = old_e[key], new_e[key]
        if a["status"] != b["status"]:
            lines.append(f"~ {key}: status {a['status']} -> {b['status']}")
        if a["type"] != b["type"]:
            lines.append(f"~ {key}: content type {a['type']} -> {b['type']}")
        for path in sorted(set(a["shape"]) | set(b["shape"])):
            if path not in b["shape"]:
                lines.append(f"~ {key}: {path} removed (was {a['shape'][path]})")
            elif path not in a["shape"]:
                lines.append(f"~ {key}: {path} added ({b['shape'][path]})")
            elif a["shape"][path] != b["shape"][path]:
                lines.append(f"~ {key}: {path} {a['shape'][path]} -> {b['shape'][path]}")
    return lines


if __name__ == "__main__":
    result = snapshot()
    if "--compare" in sys.argv:
        CURRENT.write_text(json.dumps(result, indent=1, sort_keys=True))
        differences = compare(json.loads(BASELINE.read_text()), result)
        print("\n".join(differences) if differences else "No differences from the baseline.")
        print(f"{len(differences)} difference(s); current snapshot in {CURRENT.name}")
    else:
        BASELINE.write_text(json.dumps(result, indent=1, sort_keys=True))
        print(f"Baseline written: {len(result['endpoints'])} endpoint entries, "
              f"not called: {result['rules_not_called']}")
