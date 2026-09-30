"""Temporary: the demo walk of SIMPLIFICATION_PLAN.md 5.6 through the API (deleted at the end).

    docker compose exec backend python ../demo_walk.py

Fresh database `ca_helper_walk` + seed-demo, then: signup with the code from Mailpit, register a business,
filing page (tick, choose path, mark filed with an acknowledgement -> verified), vault upload/list/download,
Find a CA -> request, CA quotes, business accepts, CA client page (document request, mark filed), pro-bono,
assistant, admin verifies a CA, Scan now. Prints one line per step; exits 1 if any step failed.
"""

import io
import re
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import api_snapshot  # same folder: load_env and the fresh database

ROOT = api_snapshot.ROOT
failures = []

GSTR3B_Q1_ACK = """Goods and Services Tax
Acknowledgement
Form GSTR-3B
GSTIN 27ABCDE1234F1Z0
Financial Year 2026-27
Tax Period: Quarter 1 (April - June)
ARN: AA2707260123456
Date of filing: 20/07/2026"""


def check(name, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)
    return ok


def pdf_of(text):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    return document.tobytes()


def mailpit_code(email):
    """The 6-digit code in the newest Mailpit message to `email`."""
    base = f"http://{os.environ.get('MAIL_SERVER', 'localhost')}:8025/api/v1"
    for _ in range(20):
        query = urllib.parse.quote(f'to:"{email}"')
        found = json.load(urllib.request.urlopen(f"{base}/search?query={query}"))
        if found["messages"]:
            message = json.load(urllib.request.urlopen(f"{base}/message/{found['messages'][0]['ID']}"))
            return re.search(r"\b(\d{6})\b", message["Text"]).group(1)
        time.sleep(0.5)
    return None


def main():
    api_snapshot.load_env()
    os.environ["APP_ENV"] = "development"
    os.environ["GEMINI_API_KEY"] = ""
    import tempfile

    os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="walk-uploads-")
    api_snapshot.fresh_database()  # the snapshot's database, dropped and created again
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
        check("seed-demo", result.exit_code == 0, result.output)

    c = app.test_client()

    def login(email, password):
        r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
        check(f"login {email}", r.status_code == 200, r.data[:200])
        return {"Authorization": "Bearer " + r.get_json()["access_token"]}

    # 1. Signup + code from Mailpit
    email = f"walk-{int(time.time())}@example.com"
    r = c.post("/api/v1/auth/signup", json={"full_name": "Walk Owner", "email": email,
                                            "password": "Walk-Password-9", "role": "business",
                                            "terms_accepted": True})
    check("signup", r.status_code == 201, r.data[:200])
    code = mailpit_code(email)
    check("code arrived in Mailpit", code is not None)
    r = c.post("/api/v1/auth/verify-email", json={"email": email, "code": code})
    check("verify email", r.status_code in (200, 204), r.data[:200])
    B = login(email, "Walk-Password-9")

    # 2. Register a business
    form = {"legal_name": "Walk Traders", "entity_type": "proprietorship", "state": "Maharashtra",
            "address": "12 Market Road, Pune", "description": "Retail shop selling household goods",
            "annual_turnover": "4500000.00", "investment_amount": "800000", "pan": "ABCDE1234F",
            "phone": "9876543210", "gst_registered": True, "gstin": "27ABCDE1234F1Z0", "gst_qrmp": True,
            "deducts_tds": False, "pays_salary_above_limit": False}
    r = c.post("/api/v1/onboarding/business", json=form, headers=B)
    check("register business", r.status_code == 201, r.data[:300])
    r = c.get("/api/v1/compliance/dashboard", headers=B)
    check("business dashboard", r.status_code == 200, r.data[:200])

    # 3. Filing page: tick, choose self, mark filed with an acknowledgement -> verified
    items = c.get("/api/v1/compliance/items", headers=B).get_json()
    q1 = next((i for i in items if i["form_code"] == "gstr_3b" and i["period_label"].startswith("Q1")), None)
    check("Q1 GSTR-3B filing exists", q1 is not None, [i["period_label"] for i in items])
    if q1:
        page = c.get(f"/api/v1/compliance/items/{q1['id']}", headers=B).get_json()
        key = page["checklist"][0]["key"] if page.get("checklist") else "general"
        r = c.post(f"/api/v1/compliance/items/{q1['id']}/checklist", json={"key": key, "ticked": True}, headers=B)
        check("tick checklist entry", r.status_code == 200, r.data[:200])
        r = c.post(f"/api/v1/compliance/items/{q1['id']}/path", json={"path": "self"}, headers=B)
        check("choose self-file", r.status_code == 200, r.data[:200])
        r = c.post(f"/api/v1/compliance/items/{q1['id']}/mark-filed", headers=B,
                   data={"file": (io.BytesIO(pdf_of(GSTR3B_Q1_ACK)), "ack.pdf", "application/pdf")},
                   content_type="multipart/form-data")
        status = r.get_json().get("filing", {}).get("status") if r.is_json else None
        check("mark filed with acknowledgement -> filed_verified", status == "filed_verified", r.data[:300])
        r = c.get(f"/api/v1/compliance/items/{q1['id']}/acknowledgement", headers=B)
        check("download acknowledgement", r.status_code == 200 and r.data.startswith(b"%PDF"), r.status_code)
        r = c.get(f"/api/v1/compliance/items/{q1['id']}/peer-insights", headers=B)
        check("peer insights", r.status_code == 200, r.data[:200])

    # 4. Vault
    r = c.post("/api/v1/documents", headers=B, content_type="multipart/form-data",
               data={"doc_type": "sales_register", "fy": "2026-27",
                     "file": (io.BytesIO(pdf_of("Sales register April 2026")), "sales.pdf", "application/pdf")})
    check("vault upload", r.status_code == 201, r.data[:300])
    docs = c.get("/api/v1/documents", headers=B).get_json()
    check("vault list", docs["total"] >= 2, docs.get("total"))
    doc_id = r.get_json()["id"] if r.status_code == 201 else None
    if doc_id:
        r = c.get(f"/api/v1/documents/{doc_id}/file", headers=B)
        check("vault download", r.status_code == 200 and r.data.startswith(b"%PDF"), r.status_code)

    # 5. Find a CA -> request (the demo CA)
    CA = login(os.environ["DEMO_CA_EMAIL"], os.environ["DEMO_CA_PASSWORD"])
    my_ca = c.get("/api/v1/marketplace/ca-profile", headers=CA).get_json()
    cas = c.get("/api/v1/marketplace/cas?service=gstr_3b", headers=B).get_json()
    check("Find a CA with a filter", cas["total"] > 0, cas)
    catalog = c.get("/api/v1/marketplace/services", headers=CA).get_json()
    r = c.put("/api/v1/marketplace/ca-services", headers=CA,
              json={"items": [{"service_id": s["id"], "price": "1500.00"} for s in catalog]})
    check("CA sets prices for every catalog service", r.status_code == 200, r.data[:300])
    r = c.get(f"/api/v1/marketplace/cas/{my_ca['id']}", headers=B)
    check("CA page", r.status_code == 200, r.data[:200])
    filings = c.get(f"/api/v1/marketplace/cas/{my_ca['id']}/requestable-filings", headers=B).get_json()
    pick = next((f for f in filings if not f["blocked_reason"] and f["options"]), None)
    check("a requestable filing", pick is not None, [(f["form_code"], f["period_label"], f["blocked_reason"]) for f in filings])
    engagement = None
    if pick:
        r = c.post("/api/v1/marketplace/engagements", headers=B, json={
            "ca_profile_id": my_ca["id"],
            "items": [{"compliance_item_id": pick["id"], "service_id": pick["options"][0]["service_id"]}]})
        check("send request", r.status_code == 201, r.data[:300])
        engagement = r.get_json() if r.status_code == 201 else None

    # 6. CA quotes, business accepts the quote -> active
    if engagement:
        prices = [{"engagement_item_id": i["id"], "price": "999.00"} for i in engagement["items"]]
        r = c.post(f"/api/v1/marketplace/engagements/{engagement['id']}/quote", headers=CA,
                   json={"reason": "More invoices than usual.", "prices": prices})
        check("CA sends a quote", r.status_code == 200 and r.get_json()["status"] == "quoted", r.data[:300])
        r = c.post(f"/api/v1/marketplace/engagements/{engagement['id']}/accept-quote", headers=B)
        check("business accepts the quote -> active", r.status_code == 200 and r.get_json()["status"] == "active",
              r.data[:300])
        business_id = c.get("/api/v1/onboarding/business", headers=B).get_json()["business"]["id"]
        r = c.get(f"/api/v1/ca-workspace/clients/{business_id}", headers=CA)
        check("CA client page", r.status_code == 200, r.data[:300])
        r = c.post(f"/api/v1/ca-workspace/clients/{business_id}/document-requests", headers=CA,
                   json={"compliance_item_id": pick["id"], "message": "Please upload the sales register."})
        check("CA asks for a document", r.status_code == 201, r.data[:300])
        requests_ = c.get("/api/v1/ca-workspace/document-requests", headers=B).get_json()
        check("business sees the request", len(requests_) >= 1, requests_)
        if requests_ and doc_id:
            r = c.post(f"/api/v1/ca-workspace/document-requests/{requests_[0]['id']}/fulfil", headers=B,
                       json={"document_id": doc_id})
            check("business fulfils the request", r.status_code == 200, r.data[:300])
        r = c.post(f"/api/v1/ca-workspace/clients/{business_id}/filings/{pick['id']}/mark-filed", headers=CA,
                   data={"acknowledgement_no": "AA2710260000001"}, content_type="multipart/form-data")
        check("CA marks filed", r.status_code == 200, r.data[:300])
        r = c.get(f"/api/v1/marketplace/my-engagements", headers=B)
        check("business engagements list", r.status_code == 200, r.data[:200])
    for path in ("/api/v1/ca-workspace/dashboard", "/api/v1/ca-workspace/clients", "/api/v1/ca-workspace/batches"):
        r = c.get(path, headers=CA)
        check(f"CA {path}", r.status_code == 200, r.data[:200])

    # 7. Pro-bono
    r = c.get("/api/v1/marketplace/pro-bono", headers=B)
    check("business pro-bono page", r.status_code == 200, r.data[:200])
    queue = c.get("/api/v1/marketplace/pro-bono-queue", headers=CA).get_json()
    check("CA pro-bono queue", isinstance(queue, dict), queue)
    waiting = queue.get("requests") or queue.get("items") or []
    if waiting:
        r = c.post(f"/api/v1/marketplace/pro-bono/{waiting[0]['id']}/accept", headers=CA)
        check("CA accepts a pro-bono request", r.status_code == 200, r.data[:300])
    else:
        print("SKIP no pro-bono request waiting in the demo data")

    # 8. Assistant (no Gemini key: the keyword fallback answers)
    r = c.post("/api/v1/assistant/ask", headers=B, json={"question": "When is GSTR-3B due?"})
    check("assistant answers", r.status_code == 200 and r.get_json().get("answer"), r.data[:300])
    r = c.get("/api/v1/assistant/history", headers=B)
    check("assistant history", r.status_code == 200 and len(r.get_json()) >= 1, r.data[:200])

    # 9. Admin verifies a CA, Scan now
    A = login(os.environ["DEMO_ADMIN_EMAIL"], os.environ["DEMO_ADMIN_PASSWORD"])
    pending = c.get("/api/v1/admin/cas?status=pending", headers=A).get_json()
    check("pending CAs listed", len(pending) >= 1, pending)
    if pending:
        r = c.post(f"/api/v1/admin/cas/{pending[0]['id']}/verify", headers=A)
        check("admin verifies a CA", r.status_code == 200, r.data[:300])
    if "--no-scan" not in sys.argv:
        r = c.post("/api/v1/admin/regulatory/scan", headers=A)
        check("Scan now", r.status_code == 200, r.data[:300])

    # 10. Notifications
    r = c.get("/api/v1/alerts/notifications", headers=B)
    check("business notification tray", r.status_code == 200, r.data[:200])

    print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
