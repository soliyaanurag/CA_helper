"""GET /api/v1/compliance/forms/<form_code>: a form's content from content/forms/ (CO6)."""

import pytest

from app.models import FormCode, UserRole

URL = "/api/v1/compliance/forms/"


@pytest.mark.parametrize("form_code", [form.value for form in FormCode])
def test_every_form_has_its_texts_and_checklist(client, make_user, auth_headers, form_code):
    user = make_user(role=UserRole.BUSINESS)

    response = client.get(URL + form_code, headers=auth_headers(user))

    assert response.status_code == 200
    body = response.get_json()
    assert body["form_code"] == form_code
    assert body["status"] in ("TODO", "DRAFT", "DONE")
    assert body["explanation"].startswith("# ")  # the front matter is gone
    assert body["instructions"].startswith("# ")
    assert "<!--" not in body["explanation"] + body["instructions"]  # writers' notes are gone
    assert len(body["checklist"]) > 0
    keys = [entry["key"] for entry in body["checklist"]]
    assert len(keys) == len(set(keys))  # keys are unique within a form
    assert any(entry["required"] for entry in body["checklist"])


def test_a_ca_can_read_it_too(client, make_user, auth_headers):
    response = client.get(URL + "gstr_3b", headers=auth_headers(make_user(role=UserRole.CA)))

    assert response.status_code == 200


def test_unknown_form_is_404(client, make_user, auth_headers):
    response = client.get(URL + "gstr_9", headers=auth_headers(make_user()))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FORM_NOT_FOUND"


def test_requires_login(client, database):
    assert client.get(URL + "itr").status_code == 401
