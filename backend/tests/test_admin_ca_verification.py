"""CA verification: certificate upload (marketplace), and the admin screens (admin)."""

import io

import pytest

from app.models import CaProfile, CaVerificationStatus, Document, UserRole

PROFILE_URL = "/api/v1/marketplace/ca-profile"
CERT_URL = PROFILE_URL + "/certificate"
ADMIN = "/api/v1/admin"
PDF = b"%PDF-1.4 certificate of practice"

PROFILE = {
    "membership_no": "123456",
    "cop_number": "COP-123",
    "city": "Pune",
    "languages": ["english"],
    "specializations": ["itr"],
    "capacity": 10,
    "years_experience": 4,
}


def upload(client, headers, data=PDF, name="cop.pdf", mime="application/pdf"):
    return client.post(
        CERT_URL,
        data={"file": (io.BytesIO(data), name, mime)},
        headers=headers,
        content_type="multipart/form-data",
    )


@pytest.fixture()
def ca(client, make_user, auth_headers):
    """A CA with a saved (pending) profile; returns (user, headers, profile id)."""
    user = make_user(role=UserRole.CA, full_name="Meera Shah")
    headers = auth_headers(user)
    profile = client.put(PROFILE_URL, json=PROFILE, headers=headers).get_json()
    return user, headers, profile["id"]


@pytest.fixture()
def admin_headers(make_user, auth_headers):
    return auth_headers(make_user(role=UserRole.ADMIN))


def status_of(database, profile_id):
    database.session.expire_all()
    return database.session.get(CaProfile, profile_id).verification_status


# --- The CA's side ----------------------------------------------------------------------


def test_a_ca_uploads_their_certificate(client, ca, database):
    user, headers, _ = ca

    response = upload(client, headers)

    assert response.status_code == 200
    assert response.get_json()["has_certificate"] is True
    document = database.session.query(Document).one()
    assert (document.owner_id, document.doc_type) == (user.id, "certificate_of_practice")


def test_a_certificate_must_be_a_pdf_jpg_or_png(client, ca):
    response = upload(client, ca[1], data=b"just text", name="cop.txt", mime="text/plain")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_a_new_certificate_sends_a_verified_ca_back_to_pending(client, ca, admin_headers, database):
    _, headers, profile_id = ca
    upload(client, headers)
    client.post(f"{ADMIN}/cas/{profile_id}/verify", headers=admin_headers)

    upload(client, headers)

    assert status_of(database, profile_id) == CaVerificationStatus.PENDING
    assert database.session.query(Document).count() == 1  # the old certificate is deleted


def test_the_pro_bono_pledge_is_saved_and_kept_when_not_sent(client, ca):
    _, headers, _ = ca

    saved = client.put(
        PROFILE_URL, json={**PROFILE, "pro_bono_slots_per_month": 2}, headers=headers
    )
    kept = client.put(PROFILE_URL, json=PROFILE, headers=headers)

    assert saved.get_json()["pro_bono_slots_per_month"] == 2
    assert kept.get_json()["pro_bono_slots_per_month"] == 2


# --- The admin's side -------------------------------------------------------------------


def test_the_pending_tab_lists_cas_waiting_for_verification(client, ca, admin_headers):
    response = client.get(f"{ADMIN}/cas?status=pending", headers=admin_headers)

    assert [row["id"] for row in response.get_json()] == [ca[2]]
    assert response.get_json()[0]["cop_number"] == "COP-123"  # admins see the numbers


def test_verifying_needs_the_certificate(client, ca, admin_headers):
    response = client.post(f"{ADMIN}/cas/{ca[2]}/verify", headers=admin_headers)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CERTIFICATE_MISSING"


def test_an_admin_verifies_a_ca_who_is_emailed(
    client, ca, admin_headers, database, mailbox
):
    _, headers, profile_id = ca
    upload(client, headers)

    response = client.post(f"{ADMIN}/cas/{profile_id}/verify", headers=admin_headers)

    assert response.get_json()["verification_status"] == "verified"
    assert response.get_json()["verified_at"] is not None
    assert mailbox[-1]["Subject"] == "Your CA Helper profile is verified"


def test_rejecting_needs_a_reason_the_ca_then_sees(client, ca, admin_headers, mailbox):
    _, headers, profile_id = ca

    no_reason = client.post(
        f"{ADMIN}/cas/{profile_id}/reject", json={"reason": " "}, headers=admin_headers
    )
    rejected = client.post(
        f"{ADMIN}/cas/{profile_id}/reject",
        json={"reason": "The CoP number does not match the certificate."},
        headers=admin_headers,
    )
    own = client.get(PROFILE_URL, headers=headers).get_json()

    assert no_reason.status_code == 422
    assert rejected.get_json()["verification_status"] == "rejected"
    assert own["rejection_reason"] == "The CoP number does not match the certificate."
    assert "does not match" in mailbox[-1].get_content()


def test_only_admins_download_the_certificate(client, ca, admin_headers, make_user, auth_headers):
    _, headers, profile_id = ca
    upload(client, headers)
    url = f"{ADMIN}/cas/{profile_id}/certificate"

    as_admin = client.get(url, headers=admin_headers)
    as_ca = client.get(url, headers=headers)
    as_business = client.get(url, headers=auth_headers(make_user(role=UserRole.BUSINESS)))

    assert as_admin.status_code == 200
    assert as_admin.data == PDF
    assert as_admin.mimetype == "application/pdf"
    assert as_ca.status_code == as_business.status_code == 403


def test_users_can_be_filtered_and_searched(client, make_user, admin_headers):
    make_user(role=UserRole.CA, full_name="Meera Shah", email="meera@example.com")
    make_user(role=UserRole.BUSINESS, full_name="Asha Rao", email="asha@example.com")

    cas = client.get(f"{ADMIN}/users?role=ca", headers=admin_headers).get_json()
    found = client.get(f"{ADMIN}/users?search=ASHA", headers=admin_headers).get_json()

    assert [user["email"] for user in cas["items"]] == ["meera@example.com"]
    assert [user["email"] for user in found["items"]] == ["asha@example.com"]


def test_stats_count_users_cas_and_engagements(client, ca, admin_headers):
    stats = client.get(f"{ADMIN}/stats", headers=admin_headers).get_json()

    assert stats["users_by_role"] == {"business": 0, "ca": 1, "admin": 1}
    assert stats["cas_by_status"]["pending"] == 1
    assert (stats["businesses"], stats["open_engagements"]) == (0, 0)


@pytest.mark.parametrize("url", ["/users", "/cas", "/stats"])
def test_admin_lists_are_for_admins_only(client, make_user, auth_headers, database, url):
    for role in (UserRole.BUSINESS, UserRole.CA):
        response = client.get(ADMIN + url, headers=auth_headers(make_user(role=role)))
        assert response.status_code == 403
