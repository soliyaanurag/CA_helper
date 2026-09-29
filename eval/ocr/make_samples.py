"""Make the OCR evaluation samples: 15 made-up documents and labels.csv.

Every name, PAN, GSTIN and number below is fictional (no real personal data). Each
document is saved in one of three ways, like the files people upload:
    pdf    a PDF with real text (PyMuPDF reads it directly)
    photo  a PNG picture of the page (Tesseract reads it)
    scan   a PDF that holds only such a picture, like a scanned page (Tesseract reads it)

Run from the repo root (it overwrites eval/ocr/samples/ and eval/ocr/labels.csv):
    conda run -n ca-helper python eval/ocr/make_samples.py
"""

import csv
from pathlib import Path

import pymupdf

HERE = Path(__file__).parent
CREATED_BY = "claude"

# (doc_id, how it is saved, doc_type, the document's text, {field: expected value}).
# Fields: ack_number, filing_date (YYYY-MM-DD), form, month, quarter, financial_year (as
# written; an ITR shows the assessment year),
# type_guess, and for registration documents gstin, pan, legal_name, state, entity_type.
SAMPLES = [
    (
        "ack-gstr3b-01",
        "pdf",
        "gstr3b_ack",
        """Goods and Services Tax
Acknowledgement
Form GSTR-3B
GSTIN 27AAAPL1234C1Z5
Financial Year 2026-27
Tax Period: August
ARN: AA270826012345X
Date of filing: 20/09/2026""",
        {
            "ack_number": "AA270826012345X",
            "filing_date": "2026-09-20",
            "form": "gstr_3b",
            "month": "8",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-gstr1-01",
        "photo",
        "gstr1_ack",
        """Goods and Services Tax
Acknowledgement
Return Type: GSTR-1
Financial Year: 2026-27
Tax Period: July
Acknowledgement Number: AA2907260456781
Date of Filing: 11-08-2026""",
        {
            "ack_number": "AA2907260456781",
            "filing_date": "2026-08-11",
            "form": "gstr_1",
            "month": "7",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-gstr3b-02",
        "scan",
        "gstr3b_ack",
        """Goods and Services Tax
Acknowledgement
Form GSTR-3B (Quarterly)
Financial Year 2026-27
Tax Period: Quarter 1 (April - June)
ARN: AA330726098765Q
Date of filing: 22/07/2026""",
        {
            "ack_number": "AA330726098765Q",
            "filing_date": "2026-07-22",
            "form": "gstr_3b",
            "quarter": "1",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-cmp08-01",
        "pdf",
        "cmp08_ack",
        """Goods and Services Tax
Acknowledgement
Form GST CMP-08
Financial Year: 2026-27
Quarter: 1
ARN: AA090726055501K
Date of Filing: 18 July 2026""",
        {
            "ack_number": "AA090726055501K",
            "filing_date": "2026-07-18",
            "form": "cmp_08",
            "quarter": "1",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-gstr4-01",
        "photo",
        "gstr4_ack",
        """Goods and Services Tax
Acknowledgement
Form GSTR-4 (Annual Return)
Financial Year 2025-26
ARN: AA240426077712M
Date of filing: 29/04/2026""",
        {
            "ack_number": "AA240426077712M",
            "filing_date": "2026-04-29",
            "form": "gstr_4",
            "financial_year": "2025-26",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-24q-01",
        "scan",
        "tds_ack",
        """Provisional Receipt
Statement of TDS on salary: Form No. 24Q
Financial Year 2026-27, Quarter Q1
Token Number: 123456789012345
Date of receipt: 25-07-2026""",
        {
            "ack_number": "123456789012345",
            "filing_date": "2026-07-25",
            "form": "tds_24q",
            "quarter": "1",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-26q-01",
        "pdf",
        "tds_ack",
        """Provisional Receipt
Statement of TDS other than salary: Form No. 26Q
Financial Year 2025-26, Quarter Q4
Provisional Receipt Number: 987654321098765
Date: 28-05-2026""",
        {
            "ack_number": "987654321098765",
            "filing_date": "2026-05-28",
            "form": "tds_26q",
            "quarter": "4",
            "financial_year": "2025-26",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-itr4-01",
        "photo",
        "itr_ack",
        """INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT
ITR-V
Assessment Year 2026-27
Form ITR-4
Acknowledgement Number: 456789012345678
Date of e-filing: 15-07-2026""",
        {
            "ack_number": "456789012345678",
            "filing_date": "2026-07-15",
            "form": "itr",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-itr3-01",
        "scan",
        "itr_ack",
        """INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT
Assessment Year 2026-27
Form ITR-3
Acknowledgement No. 567890123456789
Date of e-filing: 30-07-2026""",
        {
            "ack_number": "567890123456789",
            "filing_date": "2026-07-30",
            "form": "itr",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "ack-gstr1-02",
        "pdf",
        "gstr1_ack",
        """Goods and Services Tax
Acknowledgement
Form GSTR-1 (Quarterly, QRMP)
Financial Year 2026-27
Tax Period: Q1
ARN AA070726033321R
Filed on 2026-07-13""",
        {
            "ack_number": "AA070726033321R",
            "filing_date": "2026-07-13",
            "form": "gstr_1",
            "quarter": "1",
            "financial_year": "2026-27",
            "type_guess": "acknowledgement",
        },
    ),
    (
        "gst-cert-01",
        "photo",
        "gst_certificate",
        """Government of India
Form GST REG-06
Registration Certificate
Registration Number: 27AAACK1234M1Z9
1. Legal Name KAVERI FOODS PRIVATE LIMITED
2. Trade Name, if any KAVERI FOODS
3. Constitution of Business Private Limited Company""",
        {
            "gstin": "27AAACK1234M1Z9",
            "pan": "AAACK1234M",
            "legal_name": "KAVERI FOODS PRIVATE LIMITED",
            "state": "Maharashtra",
            "entity_type": "private_limited",
            "type_guess": "gst_certificate",
        },
    ),
    (
        "gst-cert-02",
        "scan",
        "gst_certificate",
        """Government of India
Form GST REG-06
Registration Certificate
Registration Number: 29ABCPN5678K1Z3
1. Legal Name NEHA PRINTS
2. Trade Name, if any NEHA PRINTS
3. Constitution of Business Proprietorship""",
        {
            "gstin": "29ABCPN5678K1Z3",
            "pan": "ABCPN5678K",
            "legal_name": "NEHA PRINTS",
            "state": "Karnataka",
            "entity_type": "proprietorship",
            "type_guess": "gst_certificate",
        },
    ),
    (
        "pan-card-01",
        "photo",
        "pan_card",
        """INCOME TAX DEPARTMENT
GOVT. OF INDIA
Permanent Account Number Card
AFZPK7190K
Name
RAVI KUMAR
Date of Birth
01/01/1990""",
        {
            "pan": "AFZPK7190K",
            "legal_name": "RAVI KUMAR",
            "type_guess": "pan_card",
        },
    ),
    (
        "invoice-01",
        "pdf",
        "invoice",
        """TAX INVOICE
Invoice No: INV-2026-0142
Date: 05/09/2026
Bill To: Sample Customer
HSN 1905  Biscuits  Qty 20  Rate 50.00  Amount 1000.00""",
        {"type_guess": "invoice"},
    ),
    (
        "bank-statement-01",
        "scan",
        "bank_statement",
        """Sample Bank Ltd
STATEMENT OF ACCOUNT
IFSC: SMPL0001234
Period: 01/08/2026 to 31/08/2026
Opening Balance 10,000.00
Closing Balance 12,500.00""",
        {"type_guess": "bank_statement"},
    ),
]


def _page_with(text: str):
    """A new one-page PDF with `text` on it, and the page."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    return document, page


def _file_bytes(text: str, how: str) -> tuple[bytes, str]:
    """(the file's bytes, its extension) for one of: pdf, photo, scan."""
    document, page = _page_with(text)
    if how == "pdf":
        return document.tobytes(), "pdf"
    picture = page.get_pixmap(dpi=150).tobytes("png")
    if how == "photo":
        return picture, "png"
    scan = pymupdf.open()
    scan.new_page().insert_image(scan[0].rect, stream=picture)
    return scan.tobytes(deflate=True, garbage=3), "pdf"


def main() -> None:
    samples_dir = HERE / "samples"
    samples_dir.mkdir(exist_ok=True)
    for old in samples_dir.iterdir():
        old.unlink()

    rows = []
    for doc_id, how, doc_type, text, expected in SAMPLES:
        data, extension = _file_bytes(text, how)
        (samples_dir / f"{doc_id}.{extension}").write_bytes(data)
        for field, value in expected.items():
            rows.append([doc_id, doc_type, field, value, CREATED_BY])

    with open(HERE / "labels.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["doc_id", "doc_type", "field", "expected_value", "created_by"])
        writer.writerows(rows)
    print(f"Wrote {len(SAMPLES)} samples and {len(rows)} labels.")


if __name__ == "__main__":
    main()
