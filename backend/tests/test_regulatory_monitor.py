"""The regulatory monitor (RE1-RE6): news scan, extraction, who is told, the updates page.

The network is never used: _download is replaced by a fake web (FakeWeb below), and
Gemini by a fake reply. Uses the `business_with_filings` fixture (a QRMP business in
Maharashtra with GSTR-1, GSTR-3B and ITR filings).
"""

import json
from datetime import date

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from app import (
    ca_workspace as ca_workspace_service,
    compliance as compliance_service,
    regulatory as regulatory_service,
    utils as gemini_client,
)
from app.models import (
    GstScheme,
    ItrForm,
    MsmeTier,
    NewsArticle,
    NewsSource,
    NewsSourceKind,
    Notification,
    RegulatoryChange,
    RegulatoryChangeMatch,
    RegulatoryProfile,
    User,
    UserRole,
    utcnow,
)
from app.seed import NEWS_SOURCES, seed_news_sources
from tests.test_ca_workspace_clients import engage, filing, make_ca

BASE = "/api/v1/admin/regulatory"
FEED_URL = "https://news.example.com/gst/feed/"
ROBOTS_URL = "https://news.example.com/robots.txt"

EXTENSION = (
    "GSTR-3B due date extended for September 2026",
    "The CBIC has extended the due date of GSTR-3B for September 2026 to 31 October 2026.",
)
UNRELATED = ("High Court rules on show cause notice", "A court judgment about a notice.")


def rss(*items):
    """A small RSS feed; each item is (title, description)."""
    parts = ['<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>']
    for number, (title, description) in enumerate(items, start=1):
        parts.append(
            f"<item><title>{title}</title><link>https://news.example.com/a/{number}</link>"
            f"<pubDate>Mon, 28 Sep 2026 10:00:00 +0530</pubDate>"
            f"<description>&lt;p&gt;{description}&lt;/p&gt;</description></item>"
        )
    parts.append("</channel></rss>")
    return "".join(parts)


@pytest.fixture()
def web(monkeypatch):
    """A fake internet: {url: (status, text)}; anything else is 404. Records each visit."""
    pages = {ROBOTS_URL: (200, "User-agent: *\nDisallow: /private/\n")}
    visited = []

    def fake_download(url):
        visited.append(url)
        if url in pages:
            return pages[url]
        return 404, ""

    monkeypatch.setattr(regulatory_service, "_download", fake_download)
    pages["visited"] = visited
    return pages


@pytest.fixture()
def feed_source(database):
    source = NewsSource(name="Example GST news", url=FEED_URL, kind=NewsSourceKind.RSS)
    database.session.add(source)
    database.session.commit()
    return source


@pytest.fixture()
def gemini_reply(app, monkeypatch):
    """Turn Gemini on; set the reply with gemini_reply(dict or text)."""
    state = {"reply": "{}"}

    def fake_send(prompt, want_json):
        return state["reply"]

    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client, "_send_to_gemini", fake_send)

    def set_reply(reply):
        if isinstance(reply, dict):
            reply = json.dumps(reply)
        state["reply"] = reply

    return set_reply


@pytest.fixture()
def business(business_with_filings, database):
    """The fixture business with its saved regulatory profile (QRMP, Maharashtra)."""
    database.session.add(
        RegulatoryProfile(
            business_id=business_with_filings.id,
            msme_tier=MsmeTier.MICRO,
            gst_scheme=GstScheme.REGULAR_QRMP,
            gst_registration_suggested=False,
            itr_form=ItrForm.ITR_4,
            presumptive_eligible=True,
            audit_applicable=False,
            files_24q=False,
            files_26q=False,
            roc_not_tracked=False,
            explanations={},
            rule_version="v2",
            computed_at=utcnow(),
        )
    )
    database.session.commit()
    return business_with_filings


@pytest.fixture()
def admin(make_user, auth_headers):
    return auth_headers(make_user(role=UserRole.ADMIN))


def scan(app):
    with app.app_context():
        return regulatory_service.scan_news()


def only_change(database):
    return database.session.scalars(select(RegulatoryChange)).one()


GOOD_REPLY = {
    "relevant": True,
    "change_type": "due_date_extension",
    "summary": "GSTR-3B for September 2026 can be filed until 31 October 2026.",
    "form_codes": ["gstr_3b"],
    "gst_schemes": ["regular_monthly", "regular_qrmp"],
    "entity_types": [],
    "states": [],
    "old_due_date": "2026-10-20",
    "new_due_date": "2026-10-31",
    "period": "September 2026",
}


# --- RE1: sources -------------------------------------------------------------------


def test_seed_adds_the_news_sources_once(database):
    seed_news_sources()
    seed_news_sources()
    database.session.commit()

    sources = database.session.scalars(select(NewsSource)).all()
    assert len(sources) == len(NEWS_SOURCES)


def test_admin_adds_and_switches_off_a_source(client, database, admin):
    added = client.post(
        f"{BASE}/sources",
        json={"name": "Official page", "url": "https://gov.example.in/updates", "kind": "html"},
        headers=admin,
    )
    assert added.status_code == 201
    source_id = added.get_json()["id"]

    again = client.post(
        f"{BASE}/sources",
        json={"name": "Again", "url": "https://gov.example.in/updates", "kind": "html"},
        headers=admin,
    )
    assert again.status_code == 409

    off = client.put(f"{BASE}/sources/{source_id}", json={"enabled": False}, headers=admin)
    assert off.get_json()["enabled"] is False
    assert client.get(f"{BASE}/sources", headers=admin).get_json()[0]["enabled"] is False


# --- RE2: scanning ------------------------------------------------------------------


def test_scan_saves_new_articles_once(app, database, web, feed_source):
    web[FEED_URL] = (200, rss(EXTENSION, UNRELATED))

    first = scan(app)
    second = scan(app)

    assert first["new_articles"] == 2
    assert second["new_articles"] == 0
    article = database.session.scalars(
        select(NewsArticle).where(NewsArticle.title == EXTENSION[0])
    ).one()
    assert article.content == EXTENSION[1]  # the HTML of the description is removed
    assert article.published_at is not None


def test_scan_respects_robots_txt(app, database, web, feed_source):
    web[ROBOTS_URL] = (200, "User-agent: *\nDisallow: /\n")
    web[FEED_URL] = (200, rss(EXTENSION))

    counts = scan(app)

    assert counts["blocked_by_robots"] == 1
    assert FEED_URL not in web["visited"]
    assert database.session.scalars(select(NewsArticle)).all() == []


def test_a_disabled_or_broken_source_is_skipped(app, database, web, feed_source):
    feed_source.enabled = False
    database.session.commit()
    assert scan(app)["sources"] == 0

    feed_source.enabled = True
    database.session.commit()
    web[FEED_URL] = (500, "")
    assert scan(app)["failed"] == 1


def test_an_html_page_gives_one_article_per_long_link(app, database, web):
    page_url = "https://news.example.com/updates"
    database.session.add(NewsSource(name="Updates", url=page_url, kind=NewsSourceKind.HTML))
    database.session.commit()
    web[page_url] = (
        200,
        '<a href="/home">Home</a>'
        '<a href="/n/45">Notification 45/2026: due date of GSTR-3B for September 2026 '
        "extended to 31 October 2026</a>",
    )

    scan(app)

    article = database.session.scalars(select(NewsArticle)).one()
    assert article.url == "https://news.example.com/n/45"
    assert article.title.startswith("Notification 45/2026")


# --- RE3: extraction ----------------------------------------------------------------


def test_gemini_extracts_the_change(app, database, web, feed_source, gemini_reply):
    web[FEED_URL] = (200, rss(EXTENSION, UNRELATED))
    gemini_reply(GOOD_REPLY)

    counts = scan(app)

    assert counts["changes"] == 1  # the unrelated article never reaches Gemini
    change = only_change(database)
    assert change.notified_at is not None  # sent at once (here nobody is affected)
    assert change.change_type == "due_date_extension"
    assert change.form_codes == ["gstr_3b"]
    assert change.dates == {
        "old_due_date": "2026-10-20",
        "new_due_date": "2026-10-31",
        "period": "September 2026",
    }
    assert change.affected_categories["gst_schemes"] == ["regular_monthly", "regular_qrmp"]
    assert change.affected_categories["extracted_by"] == "ai"
    assert "entity_types" not in change.affected_categories  # empty = everyone


def test_unknown_values_from_gemini_are_dropped(app, database, web, feed_source, gemini_reply):
    web[FEED_URL] = (200, rss(EXTENSION))
    reply = dict(GOOD_REPLY)
    reply.update(
        {
            "change_type": "panic",
            "form_codes": ["gstr_3b", "gstr_99"],
            "states": ["Atlantis", "Maharashtra"],
            "new_due_date": "31/10/2026",
        }
    )
    gemini_reply(reply)

    scan(app)

    change = only_change(database)
    assert change.change_type == "other"
    assert change.form_codes == ["gstr_3b"]
    assert change.affected_categories["states"] == ["Maharashtra"]
    assert "new_due_date" not in change.dates


def test_an_article_gemini_calls_irrelevant_gives_no_change(
    app, database, web, feed_source, gemini_reply
):
    web[FEED_URL] = (200, rss(EXTENSION))
    gemini_reply({"relevant": False})

    assert scan(app)["changes"] == 0


def test_without_gemini_a_keyword_change_is_saved(app, database, web, feed_source):
    web[FEED_URL] = (200, rss(EXTENSION))  # TEST_CONFIG has no Gemini key

    scan(app)

    change = only_change(database)
    assert change.summary == EXTENSION[0]
    assert change.form_codes == ["gstr_3b"]
    assert change.change_type == "due_date_extension"
    assert change.affected_categories == {"extracted_by": "keywords"}


def test_a_request_for_an_extension_is_not_called_an_extension(app, database, web, feed_source):
    web[FEED_URL] = (
        200,
        rss(("Request for extension of ITR filing deadlines", "Professionals ask for more time.")),
    )

    scan(app)

    assert only_change(database).change_type == "other"


# --- RE4 + RE5: who is told, and the updates page ------------------------------------------


@pytest.fixture()
def found(app, database, web, feed_source, gemini_reply):
    """Scan a feed with one change Gemini extracts. Create the business first to have it told."""

    def _found(reply=GOOD_REPLY):
        web[FEED_URL] = (200, rss(EXTENSION))
        gemini_reply(reply)
        scan(app)
        return only_change(database)

    return _found


def test_admin_sees_the_changes_with_their_article(client, found, admin):
    found()

    rows = client.get(f"{BASE}/changes", headers=admin)

    row = rows.get_json()[0]
    assert row["summary"] == GOOD_REPLY["summary"]
    assert row["article_title"] == EXTENSION[0]
    assert row["source_name"] == "Example GST news"
    assert row["match_count"] == 0


def test_a_change_from_gemini_tells_the_business_and_its_ca_at_once(
    client, database, business, found, admin, make_user, mailbox
):
    ca_user, profile = make_ca(make_user, database)
    engage(database, business, profile, [filing(database, form_code="gstr_3b")])

    change = found()

    rows = client.get(f"{BASE}/changes", headers=admin).get_json()
    assert rows[0]["match_count"] == 1
    assert rows[0]["notified_at"] is not None
    match = database.session.scalars(select(RegulatoryChangeMatch)).one()
    assert match.business_id == business.id
    assert match.change_id == change.id
    assert match.notified_at is not None

    owner = database.session.get(User, business.user_id)
    owner_entry = database.session.scalars(
        select(Notification).where(Notification.user_id == owner.id)
    ).one()
    assert owner_entry.title == "Regulatory update: GSTR-3B"
    assert "New due date: 2026-10-31." in owner_entry.body
    assert owner_entry.link == "/business/updates"
    assert len(mailbox) == 1  # the owner's email (sent after the commit)

    ca_entry = database.session.scalars(
        select(Notification).where(Notification.user_id == ca_user.id)
    ).one()
    assert ca_entry.link == "/ca/updates"


def test_a_change_raises_the_clients_urgency(app, database, business, found):
    found()

    with app.app_context():
        points = ca_workspace_service.regulatory_points(business.id)

    assert points == [{"reason": "Regulatory update (GSTR-3B)", "points": 15}]


def test_old_changes_no_longer_raise_urgency(app, database, business, found):
    found()

    with app.app_context():
        later = regulatory_service.active_changes_for(business.id, today=date(2027, 1, 1))

    assert later == []


def test_a_change_for_another_scheme_or_state_tells_nobody(client, database, business, found, admin):
    found({**GOOD_REPLY, "states": ["Gujarat"]})

    assert client.get(f"{BASE}/changes", headers=admin).get_json()[0]["match_count"] == 0
    assert database.session.scalars(select(Notification)).all() == []


def test_a_filed_filing_is_not_affected(client, database, business, found, admin):
    for item in compliance_service.list_filings(business):
        if item.form_code == "gstr_3b":
            item.status = "filed"
    database.session.commit()

    found()

    assert client.get(f"{BASE}/changes", headers=admin).get_json()[0]["match_count"] == 0


def test_a_change_found_by_keywords_tells_nobody(app, database, web, feed_source, business):
    web[FEED_URL] = (200, rss(EXTENSION))  # TEST_CONFIG has no Gemini key

    scan(app)

    assert only_change(database).notified_at is None
    assert database.session.scalars(select(RegulatoryChangeMatch)).all() == []
    assert database.session.scalars(select(Notification)).all() == []


UPDATES = "/api/v1/regulatory/updates"


def test_updates_show_the_changes_about_my_forms(
    client, app, database, web, feed_source, business, make_user, auth_headers
):
    ca_user, profile = make_ca(make_user, database)
    engage(database, business, profile, [filing(database, form_code="gstr_3b")])
    lonely_ca, _ = make_ca(make_user, database)
    web[FEED_URL] = (200, rss(EXTENSION))
    scan(app)  # no Gemini: found by keywords only

    owner = database.session.get(User, business.user_id)
    mine = client.get(UPDATES, headers=auth_headers(owner)).get_json()
    for_ca = client.get(UPDATES, headers=auth_headers(ca_user)).get_json()
    for_lonely_ca = client.get(UPDATES, headers=auth_headers(lonely_ca)).get_json()

    assert [row["article_title"] for row in mine] == [EXTENSION[0]]
    assert mine[0]["affected_categories"]["extracted_by"] == "keywords"
    assert mine[0]["article_url"] == "https://news.example.com/a/1"
    assert [row["id"] for row in for_ca] == [mine[0]["id"]]
    assert for_lonely_ca == []  # no clients, so no forms


def test_updates_are_for_businesses_and_cas(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.ADMIN))

    assert client.get(UPDATES, headers=headers).status_code == 403
    assert client.get(UPDATES).status_code == 401


# --- Access and the manual trigger (RE6) ---------------------------------------------


def test_only_admins_use_the_regulatory_routes(client, make_user, auth_headers):
    for role in (UserRole.BUSINESS, UserRole.CA):
        headers = auth_headers(make_user(role=role))
        assert client.get(f"{BASE}/changes", headers=headers).status_code == 403
        assert client.get(f"{BASE}/sources", headers=headers).status_code == 403
        assert client.post(f"{BASE}/scan", headers=headers).status_code == 403


def test_admin_scan_now(client, web, feed_source, admin):
    web[FEED_URL] = (200, rss(EXTENSION))

    response = client.post(f"{BASE}/scan", headers=admin)

    assert response.status_code == 200
    assert response.get_json()["new_articles"] == 1


def test_scan_command(app, database, web, feed_source):
    web[FEED_URL] = (200, rss(EXTENSION))

    result = CliRunner().invoke(app.cli, ["regulatory", "scan"])

    assert result.exit_code == 0, result.output
    assert "new articles: 1" in result.output
    assert "new changes: 1" in result.output


def test_worker_runs_the_news_scan_every_morning(app):
    from worker import build_scheduler

    job = build_scheduler(app).get_job("regulatory.scan_news")

    assert job is not None
