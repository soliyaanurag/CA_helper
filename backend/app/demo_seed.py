"""Demo data for a 10-minute walk through every flow: `flask seed-demo`.

Everything here is fictional (names, PAN, GSTIN, phone numbers, files). Run it after
`flask seed` (it runs the normal seed first). It adds, once:

- 14 businesses, all logging in with DEMO_BUSINESS_PASSWORD:
  10 micro proprietorships on regular GST (monthly or quarterly), so the peer insights
  segment "micro proprietorship" has 10 businesses; the first one is the demo business
  (DEMO_BUSINESS_EMAIL) when it has no business yet. Then a freelancer without GST, a
  partnership on the composition scheme, an LLP and a private limited company that
  deducts TDS.
- Their filings for this financial year (from the profile, as registration makes them).
  Filings due before today are mostly filed, by the business itself or through a CA,
  some late, a few left overdue; some upcoming ones have ticked checklists.
- Engagements of the demo CA in every status (requested, quoted, active, completed,
  declined, expired, cancelled), completed ones with ratings, also with the sample CAs.
- Documents (small generated PDFs) in the vaults, linked to checklist entries, and
  acknowledgements of some filed filings; document requests (open and fulfilled);
  tray notifications; a queued pro-bono request; a CA waiting for verification.

It does nothing when the demo data is already there (it looks for the first demo
business's email). One commit at the end.
"""

import io
import logging
import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from app import alerts, compliance, documents, onboarding
from app.auth import normalize_email
from app.models import (
    Business,
    CaProfile,
    CaService,
    CatalogService,
    CaVerificationStatus,
    ComplianceItemDocument,
    ComplianceStatus,
    db,
    DocumentRequest,
    DocumentRequestStatus,
    DocumentType,
    Engagement,
    EngagementItem,
    EngagementStatus,
    EntityType,
    FilingPath,
    FormCode,
    NotificationType,
    ProBonoRequest,
    ProBonoRequestStatus,
    Rating,
    RegulatoryProfile,
    today_in_india,
    User,
    UserRole,
    utcnow,
)
from app.seed import SAMPLE_CAS
from app.utils import gstin_check_character, hash_password, state_code

log = logging.getLogger(__name__)
INDIA = ZoneInfo("Asia/Kolkata")

# (owner, business name, entity type, state, turnover and investment in lakh rupees, GST:
#  "monthly", "qrmp", "composition" or None). Row n logs in as demo-biz-NN@demo.local; row 0
#  is the demo business user instead when it has no business yet.
DEMO_BUSINESSES = [
    ("Asha Rao", "Asha Traders", "P", "Maharashtra", 45, 8, "monthly"),
    ("Imran Qureshi", "Qureshi Hardware", "P", "Uttar Pradesh", 32, 6, "qrmp"),
    ("Lakshmi Nair", "Nair Spices", "P", "Kerala", 24, 4, "qrmp"),
    ("Gurpreet Singh", "Singh Auto Parts", "P", "Punjab", 41, 9, "monthly"),
    ("Meena Joshi", "Joshi Stationers", "P", "Rajasthan", 19, 3, "qrmp"),
    ("Arjun Das", "Das Electricals", "P", "West Bengal", 28, 5, "qrmp"),
    ("Kavya Reddy", "Reddy Textiles", "P", "Telangana", 47, 9.5, "monthly"),
    ("Sunil Yadav", "Yadav Dairy", "P", "Bihar", 36, 7, "monthly"),
    ("Fatima Shaikh", "Shaikh Mobile Store", "P", "Gujarat", 22, 3.5, "qrmp"),
    ("Deepak Menon", "Menon Book House", "P", "Karnataka", 39, 6.5, "monthly"),
    ("Rohan Verma", "Rohan Verma Designs", "I", "Karnataka", 12, 1.5, None),
    ("Harish Patel", "Patel and Sons", "F", "Gujarat", 90, 15, "composition"),
    ("Nisha Kapoor", "Brightpath Consulting LLP", "L", "Telangana", 180, 25, "qrmp"),
    ("Vikram Sethi", "Nimbus Foods Private Limited", "C", "Delhi", 1200, 400, "monthly"),
]
LAKH = 100_000


def _email(index: int) -> str:
    return f"demo-biz-{index:02d}@demo.local"


ENTITY_TYPES = {
    "P": EntityType.PROPRIETORSHIP,
    "I": EntityType.INDIVIDUAL,
    "F": EntityType.PARTNERSHIP,
    "L": EntityType.LLP,
    "C": EntityType.PRIVATE_LIMITED,
}
# The 4th letter of a PAN says who holds it.
PAN_HOLDER = {"P": "P", "I": "P", "F": "F", "L": "F", "C": "C"}

PENDING_CA = ("sample-ca-pending@demo.local", "Tanvi Kulkarni", "900009")


def _pdf(text: str) -> bytes:
    """A small one-page PDF showing `text` (letters, digits and spaces only)."""
    content = f"BT /F1 14 Tf 72 720 Td (Demo document: {text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return out


def _upload(owner: User, uploader: User, name: str, doc_type: DocumentType, fy=None, period=None):
    """Store a generated PDF in the owner's vault."""
    upload = FileStorage(
        io.BytesIO(_pdf(name.rsplit(".", 1)[0])), name, content_type="application/pdf"
    )
    document = documents.add_document(owner.id, uploader.id, upload, doc_type)
    document.fy = fy
    document.period_label = period
    return document


def _link(filing, document, key: str, user: User) -> None:
    """Link a file to a filing's checklist entry and tick it."""
    db.session.add(
        ComplianceItemDocument(
            compliance_item_id=filing.id,
            document_id=document.id,
            checklist_key=key,
            linked_by_id=user.id,
        )
    )
    if key != "general":
        compliance.tick_checklist_entry(filing, key)


def _at(day, hour=11):
    """A moment on `day` in Indian time, as UTC."""
    return datetime.combine(day, time(hour), tzinfo=INDIA).astimezone(ZoneInfo("UTC"))


def _pan(index: int, kind: str, name: str) -> str:
    return f"DM{chr(65 + index)}{PAN_HOLDER[kind]}{name[0].upper()}{1000 + index:04d}Z"


def _add_business(index: int, row, user: User, today) -> Business:
    _, name, kind, state, turnover, investment, gst = row
    pan = _pan(index, kind, name)
    gstin = None
    if gst is not None:
        first_14 = state_code(state) + pan + "1Z"
        gstin = first_14 + gstin_check_character(first_14)
    business = Business(
        user_id=user.id,
        legal_name=name,
        entity_type=ENTITY_TYPES[kind],
        state=state,
        address=f"12 Demo Road, {state}",
        description="Fictional business for the CA Helper demo",
        annual_turnover=Decimal(str(turnover)) * LAKH,
        investment_amount=Decimal(str(investment)) * LAKH,
        pan=pan,
        phone=f"90000{index:05d}",
        gst_registered=gst is not None,
        gstin=gstin,
        gst_composition=gst == "composition",
        gst_qrmp=gst == "qrmp",
        deducts_tds=kind == "C",
        tan=f"DELN{index:05d}Z" if kind == "C" else None,
        pays_salary_above_limit=kind == "C",
        cin_llpin="AAB-1234" if kind == "L" else ("U15400DL2020PTC000001" if kind == "C" else None),
    )
    db.session.add(business)
    db.session.flush()
    profile = RegulatoryProfile(
        business_id=business.id,
        computed_at=utcnow(),
        **onboarding.compute_profile(business, today),
    )
    db.session.add(profile)
    compliance.create_filings(business.id, profile, today)
    db.session.flush()
    return business


def _service_for(filing) -> CatalogService:
    return db.session.scalar(
        select(CatalogService)
        .where(CatalogService.form_code == filing.form_code)
        .order_by(CatalogService.sort_order)
    )


def _engage(business, ca: CaProfile, filings, status, now, **fields) -> Engagement:
    """An engagement of `ca` on `filings` in `status`."""
    engagement = Engagement(business_id=business.id, ca_profile_id=ca.id, status=status, **fields)
    engagement.requested_at = fields.get("requested_at", now - timedelta(days=3))
    db.session.add(engagement)
    db.session.flush()
    for filing in filings:
        service = _service_for(filing)
        own = db.session.scalar(
            select(CaService.price).where(
                CaService.ca_profile_id == ca.id,
                CaService.service_id == service.id,
            )
        )
        price = own or Decimal("750")
        agreed = price if status in (EngagementStatus.ACTIVE, EngagementStatus.COMPLETED) else None
        db.session.add(
            EngagementItem(
                engagement_id=engagement.id,
                compliance_item_id=filing.id,
                service_id=service.id,
                listed_price=price,
                quoted_price=price + 250 if status == EngagementStatus.QUOTED else None,
                agreed_price=agreed,
            )
        )
    if status == EngagementStatus.ACTIVE:
        compliance.mark_filings_with_ca([filing.id for filing in filings])
    return engagement


def _file_past_filings(index, business, owner, cas, today, now):
    """File most of the filings due before today: by the business itself or through a CA
    (one completed, rated engagement per CA-filed batch), some late, the newest left
    overdue for every third business. Returns the filings left overdue."""
    past = [f for f in compliance.list_filings(business) if f.due_date < today]
    via_ca = []
    overdue = []
    for number, filing in enumerate(past):
        if number == len(past) - 1 and index % 3 == 0:
            overdue.append(filing)
            continue
        pattern = (index + number) % 5
        late = (index + number) % 7 == 0 and filing.due_date + timedelta(days=4) < today
        filed_on = (
            filing.due_date + timedelta(days=4) if late else filing.due_date - timedelta(days=2)
        )
        filing.filed_at = _at(filed_on)
        filing.acknowledgement_no = f"AA{index:02d}{number:02d}{filed_on:%d%m%y}DEMO"
        if pattern < 3:
            filing.status = ComplianceStatus.FILED
            filing.filing_path = FilingPath.SELF
        else:
            filing.status = ComplianceStatus.FILED_VERIFIED
            filing.filing_path = FilingPath.CA
            filing.verified_at = filing.filed_at
            via_ca.append(filing)
    if via_ca:
        ca = cas[index % len(cas)]
        engagement = _engage(
            business,
            ca,
            via_ca,
            EngagementStatus.COMPLETED,
            now,
            requested_at=_at(via_ca[0].due_date - timedelta(days=20)),
            responded_at=_at(via_ca[0].due_date - timedelta(days=19)),
            activated_at=_at(via_ca[0].due_date - timedelta(days=19)),
            completed_at=via_ca[-1].filed_at,
        )
        db.session.add(
            Rating(
                engagement_id=engagement.id,
                stars=5 - index % 3,
                review=["Quick and clear.", "Filed on time, explained every step.", None][
                    index % 3
                ],
            )
        )
    return overdue


def _upcoming(business, form_code=None):
    """The business's filings due today or later, soonest first (optionally of one form)."""
    today = today_in_india()
    return [
        f
        for f in compliance.list_filings(business)
        if f.due_date >= today and (form_code is None or f.form_code == form_code)
    ]


def _demo_owner(today) -> tuple[User | None, str | None]:
    """The demo business user, if it exists and has no business yet."""
    email = normalize_email(os.getenv("DEMO_BUSINESS_EMAIL", ""))
    user = db.session.scalar(select(User).where(User.email == email)) if email else None
    if user is None or onboarding.business_of_user(user) is not None:
        return None, None
    return user, email


def _pending_ca(password_hash) -> None:
    """A CA who uploaded a certificate and waits for the admin (the verification demo)."""
    email, name, membership_no = PENDING_CA
    if db.session.scalar(select(User.id).where(User.email == email)):
        return
    user = User(
        email=email,
        password_hash=password_hash,
        full_name=name,
        role=UserRole.CA,
        email_verified_at=utcnow(),
    )
    db.session.add(user)
    db.session.flush()
    certificate = _upload(
        user, user, "certificate-of-practice.pdf", DocumentType.CERTIFICATE_OF_PRACTICE
    )
    db.session.add(
        CaProfile(
            user_id=user.id,
            membership_no=membership_no,
            cop_number=f"COP-{membership_no}",
            city="Pune",
            languages=["english", "marathi"],
            specializations=["itr", "gstr_3b"],
            capacity=15,
            years_experience=2,
            about="Newly qualified CA; fictional profile waiting for verification.",
            verification_status=CaVerificationStatus.PENDING,
            cop_document_id=certificate.id,
        )
    )


def seed_demo_data() -> str:
    """Add the demo data described at the top (once). Commits. Returns what it did."""
    if db.session.scalar(select(User.id).where(User.email == _email(1))):
        return "Demo data is already there; nothing added."
    password = os.getenv("DEMO_BUSINESS_PASSWORD", "")
    if not password:
        return "Set DEMO_BUSINESS_PASSWORD in .env first (the demo businesses log in with it)."
    demo_ca_user = db.session.scalar(
        select(User).where(User.email == normalize_email(os.getenv("DEMO_CA_EMAIL", "")))
    )
    demo_ca = (
        db.session.scalar(select(CaProfile).where(CaProfile.user_id == demo_ca_user.id))
        if demo_ca_user
        else None
    )
    sample_cas = []
    for email, _, _ in SAMPLE_CAS:
        sample_cas.append(
            db.session.scalar(
                select(CaProfile)
                .join(User, CaProfile.user_id == User.id)
                .where(User.email == email)
            )
        )
    if demo_ca is None or None in sample_cas:
        return (
            "Run `flask seed` with DEMO_CA_EMAIL set first (the demo CA and sample CAs are needed)."
        )

    today = today_in_india()
    now = utcnow()
    password_hash = hash_password(password)

    # 1. Businesses and their filings.
    demo_user, demo_email = _demo_owner(today)
    owners, businesses = [], []
    for index, row in enumerate(DEMO_BUSINESSES):
        if index == 0 and demo_user is not None:
            user = demo_user
        else:
            user = User(
                email=_email(index),
                password_hash=password_hash,
                full_name=row[0],
                role=UserRole.BUSINESS,
                email_verified_at=utcnow(),
                terms_accepted_at=utcnow(),
            )
            db.session.add(user)
            db.session.flush()
        owners.append(user)
        businesses.append(_add_business(index, row, user, today))

    # 2. The past: filed (self or via a CA, some late), some overdue.
    rating_cas = [demo_ca, *sample_cas]
    overdue = {}
    for index, business in enumerate(businesses):
        overdue[index] = _file_past_filings(index, business, owners[index], rating_cas, today, now)

    # 3. The demo CA's work in every engagement status.
    def next_filing(index, form):
        filings = _upcoming(businesses[index], form)
        return filings[0] if filings else None

    active_on = {}
    for index in (0, 3, 6):  # the same GSTR-3B due date for three clients: the batch view
        filings = [
            f
            for f in (next_filing(index, FormCode.GSTR_1), next_filing(index, FormCode.GSTR_3B))
            if f
        ]
        filings += overdue.get(index, [])  # a late filing makes the client urgent
        active_on[index] = filings
        _engage(
            businesses[index],
            demo_ca,
            filings,
            EngagementStatus.ACTIVE,
            now,
            responded_at=now - timedelta(days=2),
            activated_at=now - timedelta(days=2),
        )
    requested = next_filing(2, FormCode.GSTR_3B)
    _engage(
        businesses[2],
        demo_ca,
        [requested],
        EngagementStatus.REQUESTED,
        now,
        requested_at=now - timedelta(hours=18),
        expires_at=now + timedelta(hours=30),
    )
    _engage(
        businesses[4],
        demo_ca,
        [next_filing(4, FormCode.GSTR_1)],
        EngagementStatus.QUOTED,
        now,
        responded_at=now - timedelta(days=1),
        quote_reason="Your sales register has many credit notes; it takes longer.",
    )
    _engage(
        businesses[5],
        demo_ca,
        [next_filing(5, FormCode.GSTR_1)],
        EngagementStatus.DECLINED,
        now,
        responded_at=now - timedelta(days=2),
    )
    _engage(
        businesses[7],
        demo_ca,
        [next_filing(7, FormCode.GSTR_1)],
        EngagementStatus.EXPIRED,
        now,
        requested_at=now - timedelta(days=4),
        expires_at=now - timedelta(days=2),
    )
    _engage(
        businesses[8], demo_ca, [next_filing(8, FormCode.GSTR_1)], EngagementStatus.CANCELLED, now
    )

    # 4. Checklists, files and document requests.
    asha, asha_owner = businesses[0], owners[0]
    gstr_1, gstr_3b = active_on[0][0], active_on[0][1]
    fy = gstr_1.fy
    for name, doc_type, filing, key in [
        ("sales-register.pdf", DocumentType.SALES_REGISTER, gstr_1, "sales_invoices"),
        ("customer-gstins.pdf", DocumentType.OTHER, gstr_1, "customer_gstins"),
        ("purchase-invoices.pdf", DocumentType.INVOICE, gstr_3b, "purchase_invoices"),
        ("bank-statement.pdf", DocumentType.BANK_STATEMENT, gstr_3b, "general"),
    ]:
        document = _upload(asha_owner, asha_owner, name, doc_type, fy, filing.period_label)
        _link(filing, document, key, asha_owner)
    _upload(
        asha_owner, asha_owner, "gst-registration-certificate.pdf", DocumentType.GST_CERTIFICATE
    )
    _upload(asha_owner, asha_owner, "pan-card.pdf", DocumentType.PAN_CARD)
    for filing in compliance.list_filings(asha)[:2]:
        if filing.status in compliance.DONE_STATUSES:
            ack = _upload(
                asha_owner,
                asha_owner,
                f"acknowledgement-{filing.period_label}.pdf".replace(" ", "-"),
                DocumentType.ACKNOWLEDGEMENT,
                filing.fy,
                filing.period_label,
            )
            filing.acknowledgement_document_id = ack.id
    engagement_of = {}
    for engagement in db.session.scalars(
        select(Engagement).where(
            Engagement.ca_profile_id == demo_ca.id, Engagement.status == EngagementStatus.ACTIVE
        )
    ):
        engagement_of[engagement.business_id] = engagement
    hsn = _upload(
        asha_owner, asha_owner, "hsn-summary.pdf", DocumentType.OTHER, fy, gstr_1.period_label
    )
    _link(gstr_1, hsn, "hsn_summary", asha_owner)
    db.session.add_all(
        [
            DocumentRequest(
                engagement_id=engagement_of[asha.id].id,
                compliance_item_id=gstr_3b.id,
                checklist_key="gstr_2b",
                message="Please download GSTR-2B for the period from the GST portal and upload it.",
            ),
            DocumentRequest(
                engagement_id=engagement_of[asha.id].id,
                compliance_item_id=gstr_1.id,
                checklist_key="hsn_summary",
                message="I need the HSN-wise summary of your sales.",
                status=DocumentRequestStatus.FULFILLED,
                fulfilled_at=now - timedelta(hours=5),
                document_id=hsn.id,
            ),
            DocumentRequest(
                engagement_id=engagement_of[businesses[3].id].id,
                compliance_item_id=active_on[3][0].id,
                checklist_key="sales_invoices",
                message="Send all sales invoices of the month, please.",
            ),
        ]
    )
    # Upcoming filings with some documents ticked (docs pending) or all (ready).
    for index in (1, 9):
        filing = _upcoming(businesses[index], FormCode.GSTR_3B)[0]
        keys = [e["key"] for e in compliance.checklist_with_ticks(filing) if e["required"]]
        for key in keys if index == 9 else keys[:1]:
            compliance.tick_checklist_entry(filing, key)

    # 5. Tray notifications, pro-bono, a CA waiting for verification.
    alerts.notify(
        asha_owner,
        NotificationType.DEADLINE_REMINDER,
        f"GSTR-1 ({gstr_1.period_label}) is due soon",
        f"Due on {gstr_1.due_date:%d %b %Y}.",
        f"/business/compliance/{gstr_1.id}",
    )
    alerts.notify(
        asha_owner,
        NotificationType.DOCUMENT_REQUEST,
        f"Your CA asked for a document for GSTR-3B ({gstr_3b.period_label})",
        "Please download GSTR-2B for the period from the GST portal and upload it.",
        f"/business/compliance/{gstr_3b.id}",
    )
    alerts.notify(
        demo_ca_user,
        NotificationType.DOCUMENT_REQUEST,
        f"{asha.legal_name} sent the document you asked for",
        f"For GSTR-1 ({gstr_1.period_label}): HSN summary.",
        f"/ca/clients/{asha.id}",
    )
    pro_bono_filing = next_filing(10, None)
    if pro_bono_filing is not None:
        db.session.add(
            ProBonoRequest(
                business_id=businesses[10].id,
                status=ProBonoRequestStatus.QUEUED,
                note="I am a freelancer and file my ITR for the first time.",
                compliance_item_ids=[pro_bono_filing.id],
            )
        )
    if demo_ca.pro_bono_slots_per_month == 0:
        demo_ca.pro_bono_slots_per_month = 2  # so the demo CA can take the pro-bono request
    _pending_ca(password_hash)

    db.session.commit()
    who = demo_email or _email(0)
    log.info("Demo data added: %d businesses", len(businesses))
    return f"Demo data added: {len(businesses)} businesses (the richest one: {who})."
