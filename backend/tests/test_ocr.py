"""OCR (B2): reading files locally (ON12), acknowledgements proving a filing (DO8, CO10),
the document-type check (DO9) and auto-fill from a GST certificate or PAN card (ON13).

The sample files are made here with PyMuPDF: a PDF with real text, a PNG picture of
that text (read by Tesseract), and a "scanned" PDF that holds only such a picture.
Uses `business_with_filings`: a QRMP business; GSTR-3B for Q1 2026-27 (Apr-Jun) is overdue.
"""

import io
from datetime import date

import pymupdf
import pytest
from werkzeug.datastructures import FileStorage

from app.models import ComplianceItem, Document, User
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.services import compliance_service
from app.utils import ocr
from app.utils.document_text import guess_document_type, read_proof_fields, read_registration

ITEMS = "/api/v1/compliance/items"

# A made-up GSTR-3B acknowledgement for Q1 2026-27 (all numbers are fictional).
GSTR3B_Q1_ACK = """Goods and Services Tax
Acknowledgement
Form GSTR-3B
GSTIN 27ABCDE1234F1Z5
Financial Year 2026-27
Tax Period: Quarter 1 (April - June)
ARN: AA2707260123456
Date of filing: 20/07/2026"""

GST_CERTIFICATE = """Government of India
Form GST REG-06
Registration Certificate
Registration Number: 27ABCDE1234F1Z5
1. Legal Name ASHA TRADERS PRIVATE LIMITED
2. Trade Name, if any ASHA
3. Constitution of Business Private Limited Company"""


def pdf_of(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    return document.tobytes()


def png_of(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    return page.get_pixmap(dpi=200).tobytes("png")


def scanned_pdf_of(text: str) -> bytes:
    """A PDF whose page is only a picture, like a scan: PyMuPDF finds no text in it."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(page.rect, stream=png_of(text))
    return document.tobytes()


def blank_pdf() -> bytes:
    """A PDF with one empty page: nothing to read."""
    document = pymupdf.open()
    document.new_page()
    return document.tobytes()


def mime_of(name: str) -> str:
    return "image/png" if name.endswith(".png") else "application/pdf"


@pytest.fixture()
def owner(business_with_filings, database, auth_headers):
    return auth_headers(database.session.get(User, business_with_filings.user_id))


def q1_gstr3b(database) -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code="gstr_3b", period_label="Q1 2026-27")
        .one()
    )


def mark_filed(client, headers, item_id, data: bytes, name="ack.pdf", arn=None):
    form = {"file": (io.BytesIO(data), name, mime_of(name))}
    if arn is not None:
        form["acknowledgement_no"] = arn
    return client.post(
        f"{ITEMS}/{item_id}/mark-filed",
        data=form,
        headers=headers,
        content_type="multipart/form-data",
    )


# --- ON12: reading files ---------------------------------------------------------------


def test_a_pdf_with_text_is_read_directly():
    assert "AA2707260123456" in ocr.extract_text(pdf_of(GSTR3B_Q1_ACK), "application/pdf")


def test_a_photo_and_a_scanned_pdf_are_read_by_tesseract():
    assert "AA2707260123456" in ocr.extract_text(png_of(GSTR3B_Q1_ACK), "image/png")
    assert "AA2707260123456" in ocr.extract_text(scanned_pdf_of(GSTR3B_Q1_ACK), "application/pdf")


@pytest.mark.parametrize(
    ("data", "mime_type"),
    [
        (b"%PDF-1.4 not really a pdf", "application/pdf"),
        (blank_pdf(), "application/pdf"),
    ],
)
def test_unreadable_files_raise_ocr_error(data, mime_type):
    with pytest.raises(ocr.OcrError):
        ocr.extract_text(data, mime_type)


# --- The facts found in the text -------------------------------------------------------


def test_the_facts_of_an_acknowledgement():
    fields = read_proof_fields(GSTR3B_Q1_ACK, date(2026, 9, 28))

    assert fields["acknowledgement_no"] == "AA2707260123456"
    assert fields["filing_date"] == "2026-07-20"
    assert fields["form_codes"] == ["gstr_3b"]
    assert fields["financial_years"] == ["2026-27"]
    assert fields["quarters"] == [1]
    assert 7 not in fields["months"]  # the filing date's month is not a period month
    assert fields["type_guess"] == "acknowledgement"


def test_an_itr_acknowledgement():
    text = (
        "INCOME TAX RETURN ACKNOWLEDGEMENT\nAssessment Year 2027-28\nForm ITR-4\n"
        "Acknowledgement Number : 123456789012345\nDate of e-filing 15-Jul-2027"
    )
    fields = read_proof_fields(text, date(2027, 8, 1))

    assert fields["acknowledgement_no"] == "123456789012345"
    assert fields["filing_date"] == "2027-07-15"
    assert fields["form_codes"] == ["itr"]
    assert fields["financial_years"] == ["2027-28"]


def test_similar_words_are_not_forms_or_types():
    fields = read_proof_fields(
        "Arbitration award on GSTR-1A, machine learning notes", date(2026, 9, 28)
    )

    assert fields["form_codes"] == []
    assert fields["type_guess"] is None


@pytest.mark.parametrize(
    ("text", "doc_type"),
    [
        ("STATEMENT OF ACCOUNT\nOpening Balance 1,000\nIFSC SBIN0001234", "bank_statement"),
        ("TAX INVOICE\nInvoice No 42\nHSN 1905", "invoice"),
        (GST_CERTIFICATE, "gst_certificate"),
        ("Challan ITNS 281\nBSR Code 0510032", "tds_challan"),
    ],
)
def test_document_type_guess(text, doc_type):
    assert guess_document_type(text) == doc_type


def test_registration_values_from_a_gst_certificate_and_a_pan_card():
    assert read_registration(GST_CERTIFICATE) == {
        "gstin": "27ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "state": "Maharashtra",
        "legal_name": "ASHA TRADERS PRIVATE LIMITED",
        "entity_type": "private_limited",
    }
    pan_card = (
        "INCOME TAX DEPARTMENT\nPermanent Account Number Card\nABCDE1234F\n"
        "Name\nASHA RAO\nDate of Birth\n01/01/1990"
    )
    assert read_registration(pan_card) == {"pan": "ABCDE1234F", "legal_name": "ASHA RAO"}


# --- Upload hook and DO9 ---------------------------------------------------------------


def test_an_upload_keeps_only_non_personal_facts(client, owner, database):
    response = client.post(
        "/api/v1/documents",
        data={
            "doc_type": "acknowledgement",
            "file": (io.BytesIO(pdf_of(GSTR3B_Q1_ACK)), "a.pdf", "application/pdf"),
        },
        headers=owner,
        content_type="multipart/form-data",
    )

    body = response.get_json()
    assert body["ocr_status"] == "processed"
    assert body["type_warning"] is None
    document = database.session.get(Document, body["id"])
    assert document.ocr_fields["acknowledgement_no"] == "AA2707260123456"
    stored = str(document.ocr_fields)
    assert "27ABCDE1234F1Z5" not in stored and "ABCDE1234F" not in stored  # rule 4


def test_a_file_that_looks_like_another_type_is_flagged(client, owner):
    statement = pdf_of("STATEMENT OF ACCOUNT\nOpening Balance 1,000\nClosing Balance 2,000")

    body = client.post(
        "/api/v1/documents",
        data={
            "doc_type": "invoice",
            "file": (io.BytesIO(statement), "bill.pdf", "application/pdf"),
        },
        headers=owner,
        content_type="multipart/form-data",
    ).get_json()

    assert body["type_warning"] == "bank_statement"


# --- DO8 / CO10: an acknowledgement makes the filing "Filed–verified" ------------------


@pytest.mark.parametrize(
    ("data", "name"),
    [(pdf_of(GSTR3B_Q1_ACK), "ack.pdf"), (png_of(GSTR3B_Q1_ACK), "ack.png")],
    ids=["pdf", "photo"],
)
def test_a_matching_acknowledgement_verifies_the_filing(client, owner, database, data, name):
    item = q1_gstr3b(database)

    body = mark_filed(client, owner, item.id, data, name).get_json()

    assert body["filing"]["status"] == "filed_verified"
    assert body["filing"]["acknowledgement_no"] == "AA2707260123456"  # filled from the file
    verification = body["acknowledgement"]["verification"]
    assert verification == {
        "verified": True,
        "problems": [],
        "acknowledgement_no": "AA2707260123456",
        "filing_date": "2026-07-20",
    }
    assert database.session.get(ComplianceItem, item.id).verified_at is not None


def test_an_acknowledgement_for_another_filing_is_not_accepted(client, owner, database):
    gstr1 = (
        database.session.query(ComplianceItem)
        .filter_by(form_code="gstr_1", period_label="Q1 2026-27")
        .one()
    )

    body = mark_filed(client, owner, gstr1.id, pdf_of(GSTR3B_Q1_ACK)).get_json()

    assert body["filing"]["status"] == "filed"  # filed, but not verified
    assert body["acknowledgement"]["verification"]["problems"] == [
        "It does not name the form GSTR-1."
    ]


def test_the_typed_arn_must_match_the_file(client, owner, database):
    body = mark_filed(
        client, owner, q1_gstr3b(database).id, pdf_of(GSTR3B_Q1_ACK), arn="AA0000000000000"
    ).get_json()

    assert body["filing"]["status"] == "filed"
    assert body["acknowledgement"]["verification"]["problems"] == [
        "Its number (AA2707260123456) is not the one typed (AA0000000000000)."
    ]


def test_an_unreadable_acknowledgement_says_why(client, owner, database):
    body = mark_filed(client, owner, q1_gstr3b(database).id, b"%PDF-1.4 broken").get_json()

    assert body["filing"]["status"] == "filed"
    assert body["acknowledgement"]["verification"]["problems"] == ["The PDF could not be opened."]


def test_a_verified_filing_can_be_undone(client, owner, database):
    item = q1_gstr3b(database)
    mark_filed(client, owner, item.id, pdf_of(GSTR3B_Q1_ACK))

    body = client.post(f"{ITEMS}/{item.id}/unmark-filed", headers=owner).get_json()

    assert body["filing"]["status"] == "overdue"
    assert database.session.get(ComplianceItem, item.id).verified_at is None


def test_the_ca_filing_path_is_verified_too(business_with_filings, database, make_user):
    item = q1_gstr3b(database)
    item.status = ComplianceStatus.WITH_CA
    database.session.commit()
    upload = FileStorage(
        io.BytesIO(pdf_of(GSTR3B_Q1_ACK)), "ack.pdf", content_type="application/pdf"
    )

    filing = compliance_service.mark_filed_by_ca(
        business_with_filings, make_user(role=UserRole.CA), item.id, upload=upload
    )

    assert filing.status == ComplianceStatus.FILED_VERIFIED


# --- ON13: auto-fill -------------------------------------------------------------------


def autofill(client, headers, data: bytes, name="certificate.pdf"):
    return client.post(
        "/api/v1/onboarding/autofill",
        data={"file": (io.BytesIO(data), name, mime_of(name))},
        headers=headers,
        content_type="multipart/form-data",
    )


def test_autofill_reads_a_gst_certificate_and_stores_nothing(
    client, make_user, auth_headers, database
):
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    response = autofill(client, headers, pdf_of(GST_CERTIFICATE))

    assert response.status_code == 200
    assert response.get_json()["found"] == {
        "gstin": "27ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "state": "Maharashtra",
        "legal_name": "ASHA TRADERS PRIVATE LIMITED",
        "entity_type": "private_limited",
    }
    assert database.session.query(Document).count() == 0


def test_autofill_reads_a_photo(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    response = autofill(client, headers, png_of(GST_CERTIFICATE), name="certificate.png")

    assert response.get_json()["found"]["gstin"] == "27ABCDE1234F1Z5"


def test_autofill_errors(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    unreadable = autofill(client, headers, blank_pdf())
    assert unreadable.status_code == 422
    assert unreadable.get_json()["error"]["code"] == "DOCUMENT_UNREADABLE"

    wrong_type = client.post(
        "/api/v1/onboarding/autofill",
        data={"file": (io.BytesIO(b"hello"), "a.txt", "text/plain")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert wrong_type.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"

    ca = auth_headers(make_user(role=UserRole.CA))
    assert autofill(client, ca, pdf_of(GST_CERTIFICATE)).status_code == 403
