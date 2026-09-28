"""NIC activity codes: the official list (ON9) and the suggestion + confirmation (ON10).

Gemini is never really called: tests set a fake key and replace _send_to_gemini.
"""

import json

import pytest
from sqlalchemy import func, select

from app.models import NicCode, User
from app.models.enums import UserRole
from app.seed import seed_nic_codes
from app.services import onboarding_service
from app.utils import gemini_client

SUGGEST_URL = "/api/v1/onboarding/nic-suggestions"
SEARCH_URL = "/api/v1/onboarding/nic-codes"
SAVE_URL = "/api/v1/onboarding/business/nic-code"

# A few real codes from content/reference/nic_2008.csv.
SAMPLE_CODES = [
    ("10711", "Manufacture of bread"),
    ("10712", "Manufacture of biscuits, cakes, pastries, rusks etc."),
    ("10719", "Manufacture of other bakery products n.e.c."),
    ("47214", "Retail sale of bakery products, dairy products and eggs"),
    ("56302", "Tea/coffee shops"),
    ("62011", "Writing, modifying, testing of computer program to meet the needs of a client"),
]


@pytest.fixture()
def nic_codes(database):
    for code, description in SAMPLE_CODES:
        database.session.add(NicCode(code=code, description=description))
    database.session.commit()


@pytest.fixture()
def bakery(business_with_filings, database):
    """The business describes itself as a bakery; returns (business, owner)."""
    business = business_with_filings
    business.description = "We bake biscuits and cakes. Contact asha@example.com"
    database.session.commit()
    return business, database.session.get(User, business.user_id)


@pytest.fixture()
def fake_gemini(app, monkeypatch):
    """Turn Gemini "on" with a fake that returns `reply` and records what it was sent."""
    sent = []
    state = {"reply": ""}

    def fake_send(prompt, want_json):
        sent.append(prompt)
        return state["reply"]

    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client, "_send_to_gemini", fake_send)

    def answer_with(picks):
        state["reply"] = json.dumps({"picks": picks})

    answer_with.sent = sent
    answer_with.state = state
    return answer_with


def codes_of(picks):
    result = []
    for pick in picks:
        result.append((pick["code"], pick["source"]))
    return result


# --- ON9: the official list -------------------------------------------------------


def test_seed_loads_only_5_digit_codes_with_the_leading_zero_put_back(database):
    seed_nic_codes()
    database.session.commit()

    codes = set(database.session.scalars(select(NicCode.code)))
    assert len(codes) > 1000
    assert "01411" in codes  # "Raising and breeding of cattle" (was 1411 in the PDF)
    assert "14101" in codes  # garments: must not clash with the cattle code
    for code in codes:
        assert len(code) == 5


def test_seed_twice_adds_nothing(database):
    seed_nic_codes()
    database.session.commit()
    first = database.session.scalar(select(func.count(NicCode.id)))

    seed_nic_codes()
    database.session.commit()

    assert database.session.scalar(select(func.count(NicCode.id))) == first


# --- ON10: keyword shortlist ------------------------------------------------------


def test_shortlist_ranks_by_matching_words(app, nic_codes):
    with app.app_context():
        shortlist = onboarding_service.shortlist_nic_codes("We make biscuits and cakes")

    codes = []
    for nic in shortlist:
        codes.append(nic.code)
    assert codes == ["10712"]  # "biscuit" and "cake" both match; plural "s" ignored


def test_shortlist_ignores_common_words(app, nic_codes):
    with app.app_context():
        assert onboarding_service.shortlist_nic_codes("our business and other services") == []


# --- ON10: suggestions ------------------------------------------------------------


def test_gemini_picks_3_codes_from_the_shortlist(
    client, bakery, nic_codes, auth_headers, fake_gemini
):
    business, owner = bakery
    fake_gemini(
        [
            {"code": "10712", "reason": "They bake biscuits and cakes."},
            {"code": "10719", "reason": "Other bakery products."},
            {"code": "47214", "reason": "If they also sell bakery products."},
        ]
    )

    response = client.post(SUGGEST_URL, headers=auth_headers(owner))

    assert response.status_code == 200
    body = response.get_json()
    assert body["ai_used"] is True
    assert codes_of(body["picks"]) == [("10712", "ai"), ("10719", "ai"), ("47214", "ai")]
    assert body["picks"][0]["reason"] == "They bake biscuits and cakes."
    assert body["picks"][0]["description"].startswith("Manufacture of biscuits")


def test_an_invented_code_is_dropped_and_keywords_fill_the_gap(
    client, bakery, nic_codes, auth_headers, fake_gemini
):
    business, owner = bakery
    fake_gemini(
        [
            {"code": "99999", "reason": "Made up."},
            {"code": "62011", "reason": "Real code, but not in the shortlist."},
            {"code": "10712", "reason": "Biscuits and cakes."},
            {"code": "10712", "reason": "Repeated."},
        ]
    )

    body = client.post(SUGGEST_URL, headers=auth_headers(owner)).get_json()

    codes = codes_of(body["picks"])
    assert codes[0] == ("10712", "ai")
    assert len(codes) <= 3
    for code, source in codes[1:]:
        assert source == "keywords"
        assert code not in ("99999", "62011", "10712")


def test_only_the_scrubbed_description_is_sent(
    client, bakery, nic_codes, auth_headers, fake_gemini
):
    business, owner = bakery
    fake_gemini([{"code": "10712", "reason": "Biscuits."}])

    client.post(SUGGEST_URL, headers=auth_headers(owner))

    prompt = fake_gemini.sent[0]
    assert "[EMAIL]" in prompt
    assert "asha@example.com" not in prompt
    assert "Asha Traders" not in prompt  # the business name is never sent
    assert business.pan not in prompt


def test_a_reply_that_is_not_json_falls_back_to_keywords(
    client, bakery, nic_codes, auth_headers, fake_gemini
):
    business, owner = bakery
    fake_gemini.state["reply"] = "Sorry, I cannot help with that."

    body = client.post(SUGGEST_URL, headers=auth_headers(owner)).get_json()

    assert body["ai_used"] is False
    assert codes_of(body["picks"])[0] == ("10712", "keywords")


def test_without_gemini_the_keyword_matches_are_returned(client, bakery, nic_codes, auth_headers):
    business, owner = bakery  # TestingConfig has no GEMINI_API_KEY

    body = client.post(SUGGEST_URL, headers=auth_headers(owner)).get_json()

    assert body["ai_used"] is False
    assert codes_of(body["picks"])[0] == ("10712", "keywords")
    assert body["shortlist"][0]["code"] == "10712"


# --- Search and save --------------------------------------------------------------


def test_search_by_word_or_code(client, bakery, nic_codes, auth_headers):
    business, owner = bakery
    headers = auth_headers(owner)

    by_word = client.get(SEARCH_URL, query_string={"q": "bakery"}, headers=headers).get_json()
    by_code = client.get(SEARCH_URL, query_string={"q": "5630"}, headers=headers).get_json()
    too_short = client.get(SEARCH_URL, query_string={"q": "b"}, headers=headers).get_json()

    assert [row["code"] for row in by_word] == ["10719", "47214"]
    assert [row["code"] for row in by_code] == ["56302"]
    assert too_short == []


def test_save_a_code_and_read_it_back(client, bakery, nic_codes, auth_headers):
    business, owner = bakery
    headers = auth_headers(owner)

    response = client.put(SAVE_URL, json={"code": "10712"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["code"] == "10712"
    mine = client.get("/api/v1/onboarding/business", headers=headers).get_json()
    assert mine["nic_code"]["code"] == "10712"


def test_before_choosing_the_code_is_null(client, bakery, auth_headers):
    business, owner = bakery

    mine = client.get("/api/v1/onboarding/business", headers=auth_headers(owner)).get_json()

    assert mine["nic_code"] is None


def test_an_unknown_code_is_refused(client, bakery, nic_codes, auth_headers):
    business, owner = bakery

    response = client.put(SAVE_URL, json={"code": "12345"}, headers=auth_headers(owner))

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "UNKNOWN_NIC_CODE"


# --- Access -----------------------------------------------------------------------


def test_before_registering_suggestions_are_404(client, make_user, auth_headers):
    owner = make_user(role=UserRole.BUSINESS)

    response = client.post(SUGGEST_URL, headers=auth_headers(owner))

    assert response.status_code == 404


def test_ca_and_admin_cannot_use_the_nic_endpoints(client, make_user, auth_headers):
    for role in (UserRole.CA, UserRole.ADMIN):
        headers = auth_headers(make_user(role=role))
        assert client.post(SUGGEST_URL, headers=headers).status_code == 403
        search = client.get(SEARCH_URL, query_string={"q": "bread"}, headers=headers)
        assert search.status_code == 403
        assert client.put(SAVE_URL, json={"code": "10711"}, headers=headers).status_code == 403


def test_suggestions_are_rate_limited(client, bakery, nic_codes, auth_headers):
    business, owner = bakery
    headers = auth_headers(owner)

    for _ in range(10):
        assert client.post(SUGGEST_URL, headers=headers).status_code == 200

    assert client.post(SUGGEST_URL, headers=headers).status_code == 429
