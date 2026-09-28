"""Business logic for the CA marketplace: CA profiles, prices and the list businesses browse.

get_own_profile(user) -> CaProfile                  the CA's profile (404 before the first save)
save_own_profile(user, **fields) -> CaProfile        create or update it
list_verified_cas(page, page_size, ...) -> dict      verified CAs, filtered and paginated
get_verified_ca(profile_id) -> dict                  one verified CA with the services they offer
save_certificate(user, upload) -> CaProfile          upload the Certificate of Practice (-> pending)
list_catalog() -> list[dict]                         catalog services with their typical price range
get_own_menu(user) -> dict                           the services the CA offers, with prices
save_own_menu(user, items) -> dict                   replace the CA's price menu

Engagements (a business working with a CA on some filings):
list_requestable_filings(business, ca_id) -> list    the business's filings, with this CA's prices
open_filing_ids(filing_ids) -> set                   those in an open engagement (for onboarding)
create_request(business, ca_id, items) -> dict       send a request (status `requested`)
list_business_engagements(business) -> list          the business's engagements, newest first
list_ca_engagements(user) -> list                    the CA's engagements, newest first
accept_request / send_quote / decline_request / complete_engagement(user, id)    CA actions
expire_old_requests() -> int                         worker job: unanswered requests expire (MA12)

Access checks (MA14): the ONLY way to decide what a CA may see of a business (CLAUDE.md rule 5):
ca_has_active_access(ca_profile_id, business_id) -> bool     an ACTIVE engagement between them?
active_engagement_item_ids(ca_profile_id, business_id)      filings the CA works on (active)
open_engagement_item_ids(ca_profile_id, business_id)        filings in a request or active work
ca_can_access_document(ca_profile_id, document_id) -> bool  a document of one of those filings?
own_profile_id(user) -> uuid | None                          the logged-in CA's profile id

Ratings (MA17): rate_engagement(business, id, stars, review) after completion, once;
rating_summary(ca_profile_id) -> {rating_average, rating_count}; latest_reviews(ca_profile_id).

Pro-bono queue (MA16): a MICRO business asks for free help with some filings
(join_pro_bono_queue); verified CAs with free slots this month see the queue
(get_pro_bono_queue) and take a request (accept_pro_bono_request), which becomes an
`active` engagement at ₹0 with is_pro_bono. The business can cancel while queued.
accept_quote / reject_quote / withdraw_request(business, id)                    business actions

Engagement lifecycle: requested -> active (the CA accepts at the listed prices), or
requested -> quoted -> active (the business accepts the CA's quote); a request can also
end as declined (by the CA) or cancelled (the business withdraws it or rejects the
quote); active -> completed (the CA marks it done). A filing is in at most one OPEN
engagement (requested, quoted or active). When an engagement becomes active, its
filings are set to "With CA" (compliance_service.mark_filings_with_ca).

Typical price range: the min, median and max price of a service across verified CAs
with live accounts, worked out each time from `ca_services` (never typed in). It is
shown only once MIN_CAS_FOR_RANGE CAs offer the service; with fewer, one or two
prices would say little and could reveal a single CA's fee.

For the admin module: list_cas_for_admin, get_ca_for_admin, certificate_document_id,
set_verification, count_cas_by_status, count_open_engagements.

Verification: a new profile is `pending` until an admin checks it (the Certificate of
Practice must be uploaded first). A new certificate sends it back to `pending`. If a verified or
rejected CA changes the membership or CoP number, it goes back to `pending` (the
admin must check the new number). A rejected CA's profile goes back to `pending`
on any save, so fixing it and saving asks for a new check.
"""

import logging
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.errors import ApiError
from app.extensions import db
from app.models import (
    CaProfile,
    CaService,
    CatalogService,
    Engagement,
    EngagementItem,
    ProBonoRequest,
    Rating,
    User,
)
from app.models.base import today_in_india, utcnow
from app.models.compliance import ComplianceStatus
from app.models.documents import DocumentType
from app.models.enums import FormCode
from app.models.marketplace import (
    SERVICE_SPECIALIZATIONS,
    CaVerificationStatus,
    EngagementStatus,
    ProBonoRequestStatus,
)
from app.services import compliance_service, documents_service, onboarding_service
from app.utils.email import send_email

log = logging.getLogger(__name__)

# Changing one of these needs a new admin check.
IDENTITY_FIELDS = ("membership_no", "cop_number")

# The typical price range of a service is shown once this many CAs offer it.
MIN_CAS_FOR_RANGE = 3


def _only_listed_cas(stmt):
    """Keep verified CA profiles with live accounts: the CAs businesses may see.

    `stmt` must already join CaProfile and User.
    """
    return stmt.where(
        CaProfile.verification_status == CaVerificationStatus.VERIFIED,
        CaProfile.is_active,
        User.is_active,
        User.deleted_at.is_(None),
    )


def _find_profile(user: User) -> CaProfile | None:
    return db.session.scalar(
        select(CaProfile).where(CaProfile.user_id == user.id, CaProfile.is_active)
    )


def get_own_profile(user: User) -> CaProfile:
    """The logged-in CA's profile. Raises 404 CA_PROFILE_NOT_FOUND if they have not saved one."""
    profile = _find_profile(user)
    if profile is None:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "You have not completed your profile yet.")
    return profile


def save_own_profile(user: User, **fields) -> CaProfile:
    """Create or update the logged-in CA's profile with the validated `fields`.

    Raises 409 DUPLICATE_MEMBERSHIP_NO if another CA already uses that number.
    """
    profile = _find_profile(user)
    taken = db.session.scalar(
        select(CaProfile.id).where(
            CaProfile.membership_no == fields["membership_no"],
            CaProfile.user_id != user.id,
        )
    )
    if taken:
        raise ApiError(
            409,
            "DUPLICATE_MEMBERSHIP_NO",
            "Another CA has already registered this membership number.",
        )

    if profile is None:
        profile = CaProfile(user_id=user.id, verification_status=CaVerificationStatus.PENDING)
        db.session.add(profile)
        log.info("CA profile created for user %s", user.id)
    elif profile.verification_status == CaVerificationStatus.REJECTED or _identity_changed(
        profile, fields
    ):
        profile.verification_status = CaVerificationStatus.PENDING

    for name, value in fields.items():
        if value is not None:  # an older form sends no pro-bono slots: keep the saved number
            setattr(profile, name, value)
    db.session.commit()
    return profile


def _identity_changed(profile: CaProfile, fields: dict) -> bool:
    """True if the membership or CoP number in `fields` differs from the saved one."""
    changed = False
    for name in IDENTITY_FIELDS:
        if getattr(profile, name) != fields[name]:
            changed = True
    return changed


def save_certificate(user: User, upload) -> CaProfile:
    """Store the CA's Certificate of Practice (encrypted) and link it to their profile.

    A new certificate needs a new admin check: the profile goes back to `pending`
    (a verified CA leaves the marketplace until then). The old certificate is soft-deleted.
    404 CA_PROFILE_NOT_FOUND before the first profile save; storage errors pass through.
    """
    profile = get_own_profile(user)
    document = documents_service.add_document(
        user.id, user.id, upload, DocumentType.CERTIFICATE_OF_PRACTICE
    )
    db.session.flush()  # gives document.id
    if profile.cop_document_id:
        documents_service.remove_document(profile.cop_document_id)
    profile.cop_document_id = document.id
    profile.verification_status = CaVerificationStatus.PENDING
    db.session.commit()
    log.info("CA profile %s uploaded a certificate", profile.id)
    return profile


# --- For the admin module: verification and counts (none of these commits) --------------


def _admin_row(profile: CaProfile) -> dict:
    """Everything an admin sees about a CA (their numbers too, for checking)."""
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.user.full_name,
        "email": profile.user.email,
        "membership_no": profile.membership_no,
        "cop_number": profile.cop_number,
        "city": profile.city,
        "languages": profile.languages,
        "specializations": profile.specializations,
        "capacity": profile.capacity,
        "years_experience": profile.years_experience,
        "pro_bono_slots_per_month": profile.pro_bono_slots_per_month,
        "about": profile.about,
        "verification_status": profile.verification_status,
        "rejection_reason": profile.rejection_reason,
        "verified_at": profile.verified_at,
        "has_certificate": profile.cop_document_id is not None,
        "updated_at": profile.updated_at,
    }


def list_cas_for_admin(status: CaVerificationStatus | None) -> list[dict]:
    """CA profiles (optionally of one status), the longest-waiting first."""
    stmt = select(CaProfile).where(CaProfile.is_active).order_by(CaProfile.updated_at)
    if status is not None:
        stmt = stmt.where(CaProfile.verification_status == status)
    rows = []
    for profile in db.session.scalars(stmt):
        rows.append(_admin_row(profile))
    return rows


def _ca_for_admin(profile_id) -> CaProfile:
    profile = db.session.get(CaProfile, profile_id)
    if profile is None or not profile.is_active:
        raise ApiError(404, "CA_NOT_FOUND", "This CA was not found.")
    return profile


def get_ca_for_admin(profile_id) -> dict:
    return _admin_row(_ca_for_admin(profile_id))


def certificate_document_id(profile_id):
    """The document id of the CA's Certificate of Practice. 404 CERTIFICATE_MISSING."""
    profile = _ca_for_admin(profile_id)
    if profile.cop_document_id is None:
        raise ApiError(404, "CERTIFICATE_MISSING", "This CA has not uploaded a certificate.")
    return profile.cop_document_id


def set_verification(profile_id, admin: User, verified: bool, reason: str | None) -> CaProfile:
    """An admin verifies or rejects a CA. Verifying needs an uploaded certificate
    (409 CERTIFICATE_MISSING). Does not commit."""
    profile = _ca_for_admin(profile_id)
    if verified:
        if profile.cop_document_id is None:
            raise ApiError(
                409, "CERTIFICATE_MISSING", "Ask the CA to upload their certificate first."
            )
        profile.verification_status = CaVerificationStatus.VERIFIED
        profile.verified_at = utcnow()
        profile.verified_by_id = admin.id
        profile.rejection_reason = None
    else:
        profile.verification_status = CaVerificationStatus.REJECTED
        profile.rejection_reason = reason
        profile.verified_at = None
        profile.verified_by_id = None
    return profile


def count_cas_by_status() -> dict:
    """{"pending": n, "verified": n, "rejected": n} over live CA profiles."""
    counts = {"pending": 0, "verified": 0, "rejected": 0}
    for status in db.session.scalars(
        select(CaProfile.verification_status).where(CaProfile.is_active)
    ):
        counts[status.value] += 1
    return counts


def count_open_engagements() -> int:
    stmt = select(func.count()).select_from(Engagement).where(Engagement.status.in_(OPEN_STATUSES))
    return db.session.scalar(stmt)


def list_verified_cas(
    page: int,
    page_size: int,
    specialization: str | None = None,
    language: str | None = None,
    city: str | None = None,
    service: str | None = None,
    user: User | None = None,
) -> dict:
    """Verified CAs with live accounts, most experienced first.

    `specialization` / `language` keep CAs whose list contains that code; `city`
    keeps CAs whose city contains the text (any case); `service` (a catalog code)
    keeps CAs who offer that service, and each item then has their `price`.

    For a `user` with a registered business the list is ranked for it: each item also
    gets `my_prices` (the CA's price for each of the business's open filing forms) and
    `same_city` (the CA's city is in the business address); CAs offering more of those
    forms come first, then same-city CAs, then the usual order. Without a registered
    business the order and the items are as before (my_prices [], same_city null).
    """
    stmt = select(CaProfile).join(CaProfile.user)
    stmt = _only_listed_cas(stmt)
    stmt = stmt.order_by(CaProfile.years_experience.desc(), User.full_name, CaProfile.id)
    if specialization:
        stmt = stmt.where(CaProfile.specializations.contains([specialization]))
    if language:
        stmt = stmt.where(CaProfile.languages.contains([language]))
    if city and city.strip():
        stmt = stmt.where(CaProfile.city.icontains(city.strip(), autoescape=True))
    if service:
        stmt = stmt.join(CaService, CaService.ca_profile_id == CaProfile.id)
        stmt = stmt.join(CatalogService, CaService.service_id == CatalogService.id)
        stmt = stmt.where(
            CatalogService.code == service, CatalogService.is_active, CaService.is_active
        )

    business = None
    if user is not None:
        business = onboarding_service.business_of_user(user)

    # One row per CA on this page: {"profile", "my_prices", "same_city"}.
    rows = []
    if business is None:
        result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
        for profile in result.items:
            rows.append({"profile": profile, "my_prices": [], "same_city": None})
        total = result.total
    else:
        forms = set()
        for filing in compliance_service.list_filings(business):
            if filing.status not in FILED_STATUSES:
                forms.add(filing.form_code)
        itr_service_code = _itr_service_code(business)
        address = business.address.lower()
        for profile in db.session.scalars(stmt):
            rows.append(
                {
                    "profile": profile,
                    "my_prices": _my_prices(profile, forms, itr_service_code),
                    "same_city": profile.city.lower() in address,
                }
            )
        # sort() keeps the usual order (experience, name) between CAs that rank the same.
        rows.sort(key=_ranking_key)
        total = len(rows)
        # Keep only this page, e.g. page 2 with page_size 20 is rows 20 to 39.
        start = (page - 1) * page_size
        rows = rows[start : start + page_size]

    items = []
    for row in rows:
        profile = row["profile"]
        my_prices = row["my_prices"]
        same_city = row["same_city"]
        ratings = rating_summary(profile.id)
        price = None
        if service:
            price = _price_of(profile, service)
        items.append(
            {
                "id": profile.id,
                "full_name": profile.user.full_name,
                "membership_no": profile.membership_no,
                "city": profile.city,
                "languages": profile.languages,
                "specializations": profile.specializations,
                "years_experience": profile.years_experience,
                "about": profile.about,
                "price": price,
                "my_prices": my_prices,
                "same_city": same_city,
                "rating_average": ratings["rating_average"],
                "rating_count": ratings["rating_count"],
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def _my_prices(profile: CaProfile, forms: set, itr_service_code: str | None) -> list[dict]:
    """The CA's lowest price for each of `forms` they offer ({form_code, price})."""
    best = {}
    for service, price in _filing_services(profile):
        if service.form_code not in forms:
            continue
        if service.form_code == FormCode.ITR and service.code != itr_service_code:
            continue
        if service.form_code not in best or price < best[service.form_code]:
            best[service.form_code] = price
    result = []
    for form, price in best.items():
        result.append({"form_code": form, "price": price})
    return result


def _ranking_key(row: dict):
    """Sort order for a business: CAs offering more of its filings first, then same-city CAs.

    Python sorts small values first, so the count is negated (-3 comes before -1) and
    `not same_city` is False (= 0) for a same-city CA.
    """
    return (-len(row["my_prices"]), not row["same_city"])


def _price_of(profile: CaProfile, service_code: str):
    """The CA's current price for a catalog service, or None if they do not offer it."""
    stmt = (
        select(CaService.price)
        .join(CatalogService, CaService.service_id == CatalogService.id)
        .where(
            CaService.ca_profile_id == profile.id,
            CaService.is_active,
            CatalogService.code == service_code,
        )
    )
    return db.session.scalar(stmt)


# --- Service catalog and CA prices ------------------------------------------------


def _prices_by_service() -> dict:
    """{service_id: [prices]} of every verified CA with a live account."""
    stmt = (
        select(CaService.service_id, CaService.price)
        .join(CaProfile, CaService.ca_profile_id == CaProfile.id)
        .join(User, CaProfile.user_id == User.id)
        .where(CaService.is_active)
    )
    stmt = _only_listed_cas(stmt)

    prices = {}
    for service_id, price in db.session.execute(stmt):
        if service_id not in prices:
            prices[service_id] = []
        prices[service_id].append(price)
    return prices


def list_catalog() -> list[dict]:
    """Every active catalog service, in catalog order, with its typical price range."""
    services = db.session.scalars(
        select(CatalogService).where(CatalogService.is_active).order_by(CatalogService.sort_order)
    ).all()
    prices = _prices_by_service()

    result = []
    for service in services:
        service_prices = prices.get(service.id, [])
        row = {
            "id": service.id,
            "code": service.code,
            "name": service.name,
            "description": service.description,
            "unit": service.unit,
            "specialization": SERVICE_SPECIALIZATIONS.get(service.code),
            "ca_count": len(service_prices),
            "min_price": None,
            "median_price": None,
            "max_price": None,
        }
        if len(service_prices) >= MIN_CAS_FOR_RANGE:
            row["min_price"] = min(service_prices)
            row["median_price"] = median(service_prices)
            row["max_price"] = max(service_prices)
        result.append(row)
    return result


def _menu_of(profile: CaProfile) -> dict:
    """The services a CA offers now, as {"items": [{service_id, price}]}. Does not commit."""
    rows = db.session.scalars(
        select(CaService).where(CaService.ca_profile_id == profile.id, CaService.is_active)
    ).all()
    items = []
    for row in rows:
        items.append({"service_id": row.service_id, "price": row.price})
    return {"items": items}


def get_own_menu(user: User) -> dict:
    """The logged-in CA's price menu. Empty until they have a profile and set prices."""
    profile = _find_profile(user)
    if profile is None:
        return {"items": []}
    return _menu_of(profile)


def save_own_menu(user: User, items: list[dict]) -> dict:
    """Replace the CA's price menu with `items` ([{service_id, price}]).

    Services left out are no longer offered (soft delete); offering one again later
    brings its row back. Raises 404 CA_PROFILE_NOT_FOUND without a profile, and
    400 UNKNOWN_SERVICE for a service that is not in the active catalog.
    """
    profile = get_own_profile(user)

    new_prices = {}
    for item in items:
        new_prices[item["service_id"]] = item["price"]

    for service_id in new_prices:
        service = db.session.get(CatalogService, service_id)
        if service is None or not service.is_active:
            raise ApiError(400, "UNKNOWN_SERVICE", "One of the services is not in the catalog.")

    # Update the rows the CA already has (offered now or before).
    old_rows = db.session.scalars(
        select(CaService).where(CaService.ca_profile_id == profile.id)
    ).all()
    for row in old_rows:
        if row.service_id in new_prices:
            row.price = new_prices[row.service_id]
            row.is_active = True
            row.deleted_at = None
            del new_prices[row.service_id]
        elif row.is_active:
            row.is_active = False
            row.deleted_at = utcnow()

    # Whatever is left is offered for the first time.
    for service_id, price in new_prices.items():
        db.session.add(CaService(ca_profile_id=profile.id, service_id=service_id, price=price))

    db.session.commit()
    log.info("CA %s saved a price menu with %d services", profile.id, len(items))
    return _menu_of(profile)


def _find_listed_ca(profile_id) -> CaProfile:
    """A CA businesses may see (verified, live account). Raises 404 CA_NOT_FOUND otherwise."""
    stmt = select(CaProfile).join(CaProfile.user).where(CaProfile.id == profile_id)
    stmt = _only_listed_cas(stmt)
    profile = db.session.scalar(stmt)
    if profile is None:
        raise ApiError(404, "CA_NOT_FOUND", "This CA is not listed on the marketplace.")
    return profile


def get_verified_ca(profile_id) -> dict:
    """One listed CA's public details and the services they offer, in catalog order.

    Each service has the CA's price and the typical range, so the page can compare
    them. Raises 404 CA_NOT_FOUND for a CA businesses may not see (not verified, or
    the account is deactivated), exactly like the list.
    """
    profile = _find_listed_ca(profile_id)

    # The CA's current prices, by catalog service id.
    my_prices = {}
    for row in db.session.scalars(
        select(CaService).where(CaService.ca_profile_id == profile.id, CaService.is_active)
    ):
        my_prices[row.service_id] = row.price

    services = []
    for service in list_catalog():
        if service["id"] in my_prices:
            offered = dict(service)  # a copy with the typical range, plus this CA's price
            offered["price"] = my_prices[service["id"]]
            services.append(offered)

    ratings = rating_summary(profile.id)
    return {
        "id": profile.id,
        "full_name": profile.user.full_name,
        "membership_no": profile.membership_no,
        "city": profile.city,
        "languages": profile.languages,
        "specializations": profile.specializations,
        "years_experience": profile.years_experience,
        "about": profile.about,
        "services": services,
        "rating_average": ratings["rating_average"],
        "rating_count": ratings["rating_count"],
        "reviews": latest_reviews(profile.id),
    }


# --- Engagements: requests, answers and the lifecycle (MA9, MA10, MA11, MA13) --------

# An engagement in one of these still holds its filings: nobody may request them again.
OPEN_STATUSES = [EngagementStatus.REQUESTED, EngagementStatus.QUOTED, EngagementStatus.ACTIVE]

# Filings in these states are done: there is nothing left for a CA to do.
FILED_STATUSES = [ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED]

# A CA has this long to answer a request. After that, expire_old_requests() (a worker
# job, MA12) marks it `expired` and the CA can no longer accept, quote or decline it.
ANSWER_WITHIN = timedelta(hours=48)

# The one catalog service (seed.SERVICE_CATALOG code) that fits each ITR form, so an ITR
# filing is only ever priced with the service for the business's own form.
ITR_SERVICE_CODES = {
    "itr_3": "itr_business",
    "itr_4": "itr_presumptive",
    "itr_5": "itr_firm_company",
    "itr_6": "itr_firm_company",
}


def _itr_service_code(business) -> str | None:
    """The catalog code of the ITR service that fits the business's profile."""
    return ITR_SERVICE_CODES.get(onboarding_service.get_itr_form(business))


def _fits(service: CatalogService, filing, itr_service_code: str | None) -> bool:
    """True if `service` is for this filing; for ITR, only the service of the business's form."""
    if service.form_code != filing.form_code:
        return False
    return filing.form_code != FormCode.ITR or service.code == itr_service_code


def _busy_filing_ids(filing_ids) -> set:
    """The filings among `filing_ids` that are already in an open engagement."""
    stmt = (
        select(EngagementItem.compliance_item_id)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .where(
            EngagementItem.compliance_item_id.in_(filing_ids),
            Engagement.status.in_(OPEN_STATUSES),
        )
    )
    return set(db.session.scalars(stmt))


def open_filing_ids(filing_ids) -> set:
    """The filings among `filing_ids` in an open engagement (used by onboarding: a profile
    edit never removes them)."""
    return _busy_filing_ids(filing_ids)


def _filing_services(ca: CaProfile) -> list:
    """The CA's current services that are for a filing, as (CatalogService, price) pairs."""
    stmt = (
        select(CatalogService, CaService.price)
        .join(CaService, CaService.service_id == CatalogService.id)
        .where(
            CaService.ca_profile_id == ca.id,
            CaService.is_active,
            CatalogService.is_active,
            CatalogService.form_code.is_not(None),
        )
        .order_by(CatalogService.sort_order)
    )
    return db.session.execute(stmt).all()


def list_requestable_filings(business, ca_profile_id) -> list[dict]:
    """The business's filings, each with this CA's price options, soonest due first.

    `blocked_reason` says why a filing cannot be picked (None when it can).
    """
    ca = _find_listed_ca(ca_profile_id)
    services = _filing_services(ca)
    itr_service_code = _itr_service_code(business)
    filings = compliance_service.list_filings(business)
    filing_ids = []
    for filing in filings:
        filing_ids.append(filing.id)
    busy = _busy_filing_ids(filing_ids)

    result = []
    for filing in filings:
        options = []
        for service, price in services:
            if _fits(service, filing, itr_service_code):
                options.append({"service_id": service.id, "name": service.name, "price": price})

        blocked_reason = None
        if filing.status in FILED_STATUSES:
            blocked_reason = "Already filed."
        elif filing.id in busy:
            blocked_reason = "Already requested from a CA or with a CA."
        elif len(options) == 0 and filing.form_code == FormCode.ITR:
            blocked_reason = "This CA has not listed a price for the ITR of your business type."
        elif len(options) == 0:
            blocked_reason = "This CA has not listed a price for this filing."

        result.append(
            {
                "id": filing.id,
                "form_code": filing.form_code,
                "period_label": filing.period_label,
                "due_date": filing.due_date,
                "status": filing.status,
                "options": options,
                "blocked_reason": blocked_reason,
            }
        )
    return result


def create_request(business, ca_profile_id, items: list[dict]) -> dict:
    """The business asks the CA to do some filings: a new engagement, status `requested`.

    `items` is [{compliance_item_id, service_id}]; the price of each filing is copied
    from the CA's menu now. The CA gets an email. Errors: 404 CA_NOT_FOUND,
    404 FILING_NOT_FOUND, 400 DUPLICATE_FILING, 409 FILING_ALREADY_FILED,
    409 FILING_ALREADY_REQUESTED, 400 SERVICE_NOT_OFFERED (also for an ITR service
    that does not fit the business's ITR form).
    """
    ca = _find_listed_ca(ca_profile_id)
    itr_service_code = _itr_service_code(business)

    # {filing id: the service chosen for it}
    chosen = {}
    for item in items:
        if item["compliance_item_id"] in chosen:
            raise ApiError(400, "DUPLICATE_FILING", "The same filing is in the request twice.")
        chosen[item["compliance_item_id"]] = item["service_id"]

    # Lock the filings first, so a second request at the same moment waits for this one.
    filings = compliance_service.get_filings_by_ids(list(chosen), lock=True)
    busy = _busy_filing_ids(list(chosen))

    # {service id: (CatalogService, the CA's price)}
    offered = {}
    for service, price in _filing_services(ca):
        offered[service.id] = (service, price)

    for filing_id, service_id in chosen.items():
        filing = filings.get(filing_id)
        if filing is None or filing.business_id != business.id:
            raise ApiError(404, "FILING_NOT_FOUND", "One of the filings was not found.")
        if filing.status in FILED_STATUSES:
            raise ApiError(409, "FILING_ALREADY_FILED", f"{filing.period_label} is already filed.")
        if filing_id in busy:
            raise ApiError(
                409,
                "FILING_ALREADY_REQUESTED",
                f"{filing.period_label} is already requested from a CA or with a CA.",
            )
        if service_id not in offered or not _fits(offered[service_id][0], filing, itr_service_code):
            raise ApiError(
                400, "SERVICE_NOT_OFFERED", "This CA does not offer that service for this filing."
            )

    now = utcnow()
    engagement = Engagement(
        business_id=business.id,
        ca_profile_id=ca.id,
        status=EngagementStatus.REQUESTED,
        requested_at=now,
        expires_at=now + ANSWER_WITHIN,
    )
    db.session.add(engagement)
    db.session.flush()  # gives engagement.id
    for filing_id, service_id in chosen.items():
        db.session.add(
            EngagementItem(
                engagement_id=engagement.id,
                compliance_item_id=filing_id,
                service_id=service_id,
                listed_price=offered[service_id][1],
            )
        )
    db.session.commit()
    log.info("Engagement %s requested with %d filings", engagement.id, len(chosen))

    send_email(
        ca.user.email,
        "New request on CA Helper",
        "engagement_requested",
        ca_name=ca.user.full_name,
        business_name=business.legal_name,
        filing_count=len(chosen),
    )
    return _engagement_details(engagement)


def _items_of(engagement: Engagement) -> list[EngagementItem]:
    """The engagement's filings, in the order they were requested."""
    stmt = (
        select(EngagementItem)
        .where(EngagementItem.engagement_id == engagement.id)
        .order_by(EngagementItem.created_at)
    )
    return db.session.scalars(stmt).all()


def _engagement_details(engagement: Engagement) -> dict:
    """One engagement as both sides see it: the CA, the business, the filings and prices."""
    ca = db.session.get(CaProfile, engagement.ca_profile_id)
    business = onboarding_service.get_business(engagement.business_id)
    rows = _items_of(engagement)

    filing_ids = []
    for row in rows:
        filing_ids.append(row.compliance_item_id)
    filings = compliance_service.get_filings_by_ids(filing_ids)

    items = []
    for row in rows:
        service = db.session.get(CatalogService, row.service_id)
        filing = filings.get(row.compliance_item_id)  # None if the filing was removed
        items.append(
            {
                "id": row.id,
                "compliance_item_id": row.compliance_item_id,
                "form_code": filing.form_code if filing else None,
                "period_label": filing.period_label if filing else None,
                "due_date": filing.due_date if filing else None,
                "service_name": service.name,
                "listed_price": row.listed_price,
                "quoted_price": row.quoted_price,
                "agreed_price": row.agreed_price,
            }
        )

    return {
        "id": engagement.id,
        "status": engagement.status,
        "ca_profile_id": ca.id,
        "ca_name": ca.user.full_name,
        "business_name": business.legal_name,
        "quote_reason": engagement.quote_reason,
        "requested_at": engagement.requested_at,
        "expires_at": engagement.expires_at,
        "responded_at": engagement.responded_at,
        "activated_at": engagement.activated_at,
        "completed_at": engagement.completed_at,
        "items": items,
        "rating": _rating_of(engagement),
        "is_pro_bono": engagement.is_pro_bono,
    }


def list_business_engagements(business) -> list[dict]:
    """Every engagement of the business, newest first."""
    stmt = (
        select(Engagement)
        .where(Engagement.business_id == business.id)
        .order_by(Engagement.requested_at.desc())
    )
    result = []
    for engagement in db.session.scalars(stmt):
        result.append(_engagement_details(engagement))
    return result


def list_ca_engagements(user: User) -> list[dict]:
    """Every engagement of the logged-in CA, newest first (empty without a profile)."""
    ca = _find_profile(user)
    if ca is None:
        return []
    stmt = (
        select(Engagement)
        .where(Engagement.ca_profile_id == ca.id)
        .order_by(Engagement.requested_at.desc())
    )
    result = []
    for engagement in db.session.scalars(stmt):
        result.append(_engagement_details(engagement))
    return result


# --- Engagement actions ------------------------------------------------------------


def _ca_engagement(user: User, engagement_id) -> Engagement:
    """One of the logged-in CA's engagements. 404 ENGAGEMENT_NOT_FOUND for anyone else's."""
    engagement = db.session.get(Engagement, engagement_id)
    ca = _find_profile(user)
    if engagement is None or ca is None or engagement.ca_profile_id != ca.id:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    return engagement


def _business_engagement(business, engagement_id) -> Engagement:
    """One of the business's engagements. 404 ENGAGEMENT_NOT_FOUND for anyone else's."""
    engagement = db.session.get(Engagement, engagement_id)
    if engagement is None or engagement.business_id != business.id:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    return engagement


def _check_status(engagement: Engagement, expected: EngagementStatus) -> None:
    """409 INVALID_STATUS unless the engagement is in the `expected` status."""
    if engagement.status != expected:
        raise ApiError(
            409,
            "INVALID_STATUS",
            f"This engagement is {engagement.status.value}, so this is no longer possible.",
        )


def _activate(engagement: Engagement, items: list[EngagementItem]) -> None:
    """Start the work: status `active`, and the filings are "With CA". Does not commit."""
    engagement.status = EngagementStatus.ACTIVE
    engagement.activated_at = utcnow()
    filing_ids = []
    for item in items:
        filing_ids.append(item.compliance_item_id)
    compliance_service.mark_filings_with_ca(filing_ids)


def _email_business(engagement: Engagement, subject: str, template: str, **context) -> None:
    """Email the owner of the engagement's business (call after committing)."""
    business = onboarding_service.get_business(engagement.business_id)
    owner = db.session.get(User, business.user_id)
    ca = db.session.get(CaProfile, engagement.ca_profile_id)
    send_email(
        owner.email,
        subject,
        template,
        owner_name=owner.full_name,
        ca_name=ca.user.full_name,
        **context,
    )


def _check_not_expired(engagement: Engagement) -> None:
    """409 REQUEST_EXPIRED once the 48 hours to answer have passed.

    The worker marks such requests `expired` every few minutes; this check also stops
    a CA who answers in the minutes before the worker runs.
    """
    if engagement.expires_at is not None and engagement.expires_at <= utcnow():
        raise ApiError(
            409, "REQUEST_EXPIRED", "This request expired: it was not answered within 48 hours."
        )


def accept_request(user: User, engagement_id) -> dict:
    """The CA accepts at the listed prices: status `active`."""
    engagement = _ca_engagement(user, engagement_id)
    _check_status(engagement, EngagementStatus.REQUESTED)
    _check_not_expired(engagement)
    items = _items_of(engagement)
    for item in items:
        item.agreed_price = item.listed_price
    engagement.responded_at = utcnow()
    _activate(engagement, items)
    db.session.commit()
    _email_business(engagement, "Your CA accepted your request", "engagement_accepted")
    return _engagement_details(engagement)


def send_quote(user: User, engagement_id, reason: str, prices: list[dict]) -> dict:
    """The CA sends a new price for every filing, with a reason: status `quoted`.

    `prices` is [{engagement_item_id, price}] and must cover every filing of the request
    (400 QUOTE_INCOMPLETE otherwise).
    """
    engagement = _ca_engagement(user, engagement_id)
    _check_status(engagement, EngagementStatus.REQUESTED)
    _check_not_expired(engagement)
    items = _items_of(engagement)

    new_prices = {}
    for entry in prices:
        new_prices[entry["engagement_item_id"]] = entry["price"]
    for item in items:
        if item.id not in new_prices:
            raise ApiError(
                400, "QUOTE_INCOMPLETE", "Enter a new price for every filing in the request."
            )
    if len(new_prices) != len(items):
        raise ApiError(
            400, "QUOTE_INCOMPLETE", "The quote has a filing that is not in the request."
        )

    for item in items:
        item.quoted_price = new_prices[item.id]
    engagement.quote_reason = reason
    engagement.status = EngagementStatus.QUOTED
    engagement.responded_at = utcnow()
    db.session.commit()
    _email_business(engagement, "Your CA sent you a quote", "engagement_quoted", reason=reason)
    return _engagement_details(engagement)


def decline_request(user: User, engagement_id) -> dict:
    """The CA declines: status `declined`; the filings are free to request again."""
    engagement = _ca_engagement(user, engagement_id)
    _check_status(engagement, EngagementStatus.REQUESTED)
    _check_not_expired(engagement)
    engagement.status = EngagementStatus.DECLINED
    engagement.responded_at = utcnow()
    db.session.commit()
    _email_business(engagement, "Your CA declined your request", "engagement_declined")
    return _engagement_details(engagement)


def complete_engagement(user: User, engagement_id) -> dict:
    """The CA marks the work as done: status `completed`."""
    engagement = _ca_engagement(user, engagement_id)
    _check_status(engagement, EngagementStatus.ACTIVE)
    engagement.status = EngagementStatus.COMPLETED
    engagement.completed_at = utcnow()
    db.session.commit()
    return _engagement_details(engagement)


def accept_quote(business, engagement_id) -> dict:
    """The business accepts the CA's quote: the quoted prices are agreed, status `active`."""
    engagement = _business_engagement(business, engagement_id)
    _check_status(engagement, EngagementStatus.QUOTED)
    items = _items_of(engagement)
    for item in items:
        item.agreed_price = item.quoted_price
    _activate(engagement, items)
    db.session.commit()
    return _engagement_details(engagement)


def reject_quote(business, engagement_id) -> dict:
    """The business rejects the CA's quote: status `cancelled`; the filings are free again."""
    engagement = _business_engagement(business, engagement_id)
    _check_status(engagement, EngagementStatus.QUOTED)
    engagement.status = EngagementStatus.CANCELLED
    db.session.commit()
    return _engagement_details(engagement)


def withdraw_request(business, engagement_id) -> dict:
    """The business withdraws a request the CA has not answered: status `cancelled`."""
    engagement = _business_engagement(business, engagement_id)
    _check_status(engagement, EngagementStatus.REQUESTED)
    engagement.status = EngagementStatus.CANCELLED
    db.session.commit()
    return _engagement_details(engagement)


# --- Request expiry (MA12): run by the worker, see backend/worker.py ------------------


def expire_old_requests() -> int:
    """Requests the CA did not answer within 48 hours become `expired`. Returns how many.

    Only `requested` engagements expire; a `quoted` one waits for the business. The
    filings are free again at once (`expired` is not an open status). After the commit,
    each business is emailed so it can pick another CA.
    """
    stmt = select(Engagement).where(
        Engagement.status == EngagementStatus.REQUESTED,
        Engagement.expires_at <= utcnow(),
    )
    expired = db.session.scalars(stmt).all()
    for engagement in expired:
        engagement.status = EngagementStatus.EXPIRED
    db.session.commit()

    for engagement in expired:
        _email_business(
            engagement,
            "Your CA request expired",
            "engagement_expired",
            service_names=_service_names(engagement),
        )
    if len(expired) > 0:
        log.info("Expired %d unanswered request(s)", len(expired))
    return len(expired)


def _service_names(engagement: Engagement) -> str:
    """The services of an engagement, e.g. "GSTR-3B filing, GSTR-1 filing"."""
    names = []
    for item in _items_of(engagement):
        service = db.session.get(CatalogService, item.service_id)
        if service.name not in names:
            names.append(service.name)
    return ", ".join(names)


# --- Access checks (MA14): what a CA may see of a business ------------------------------
# docs/DATA_MODEL.md, "Who may read what". Only an ACTIVE engagement gives access to the
# business's data, and only to the filings in it. After the engagement ends (completed,
# declined, expired, cancelled) the CA sees nothing of that business any more.


def own_profile_id(user: User):
    """The logged-in CA's profile id, or None if they have not saved a profile."""
    profile = _find_profile(user)
    if profile is None:
        return None
    return profile.id


def ca_has_active_access(ca_profile_id, business_id) -> bool:
    """True while the CA has an ACTIVE engagement with the business."""
    stmt = select(Engagement.id).where(
        Engagement.ca_profile_id == ca_profile_id,
        Engagement.business_id == business_id,
        Engagement.status == EngagementStatus.ACTIVE,
    )
    return db.session.scalar(stmt) is not None


def _item_ids(ca_profile_id, business_id, statuses) -> set:
    """The filings in this CA's engagements with this business that have one of `statuses`."""
    stmt = (
        select(EngagementItem.compliance_item_id)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .where(
            Engagement.ca_profile_id == ca_profile_id,
            Engagement.business_id == business_id,
            Engagement.status.in_(statuses),
        )
    )
    return set(db.session.scalars(stmt))


def active_engagement_item_ids(ca_profile_id, business_id) -> set:
    """The filings the CA works on for this business (in ACTIVE engagements only).

    A business may have two CAs (e.g. one for GST, one for ITR): each sees only their own.
    """
    return _item_ids(ca_profile_id, business_id, [EngagementStatus.ACTIVE])


def open_engagement_item_ids(ca_profile_id, business_id) -> set:
    """The filings in the CA's open engagements with this business (requested, quoted or
    active): what a CA may see a summary of while deciding on a request."""
    return _item_ids(ca_profile_id, business_id, OPEN_STATUSES)


def ca_can_access_document(ca_profile_id, document_id) -> bool:
    """True only for a document linked to a filing of one of the CA's ACTIVE engagements:
    a document attached to the filing, or the filing's acknowledgement."""
    stmt = (
        select(EngagementItem.compliance_item_id)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .where(
            Engagement.ca_profile_id == ca_profile_id,
            Engagement.status == EngagementStatus.ACTIVE,
        )
    )
    filing_ids = set(db.session.scalars(stmt))
    if len(filing_ids) == 0:
        return False

    allowed = documents_service.document_ids_for_filings(filing_ids)
    for filing in compliance_service.get_filings_by_ids(filing_ids).values():
        if filing.acknowledgement_document_id is not None:
            allowed.add(filing.acknowledgement_document_id)
    return document_id in allowed


# --- Ratings (MA17) --------------------------------------------------------------------

# How many of a CA's latest reviews the CA page shows.
REVIEWS_SHOWN = 5


def _rating_of(engagement: Engagement):
    """The engagement's rating as {stars, review, created_at}, or None before it is rated."""
    rating = db.session.scalar(select(Rating).where(Rating.engagement_id == engagement.id))
    if rating is None:
        return None
    return {"stars": rating.stars, "review": rating.review, "created_at": rating.created_at}


def rate_engagement(business, engagement_id, stars: int, review: str) -> dict:
    """The business rates a completed engagement: 1 to 5 stars and an optional review.

    Only once (409 ALREADY_RATED) and only after the CA marked it completed
    (409 INVALID_STATUS). Another business's engagement → 404.
    """
    engagement = _business_engagement(business, engagement_id)
    _check_status(engagement, EngagementStatus.COMPLETED)
    if _rating_of(engagement) is not None:
        raise ApiError(409, "ALREADY_RATED", "You have already rated this CA for this work.")

    review = review.strip()
    if review == "":
        review = None
    db.session.add(Rating(engagement_id=engagement.id, stars=stars, review=review))
    db.session.commit()
    log.info("Engagement %s rated %d stars", engagement.id, stars)
    return _engagement_details(engagement)


def _ratings_of_ca(ca_profile_id) -> list:
    """All ratings of the CA's engagements, newest first."""
    stmt = (
        select(Rating)
        .join(Engagement, Rating.engagement_id == Engagement.id)
        .where(Engagement.ca_profile_id == ca_profile_id)
        .order_by(Rating.created_at.desc())
    )
    return db.session.scalars(stmt).all()


def rating_summary(ca_profile_id) -> dict:
    """{"rating_average": 4.3 (one decimal) or None before any rating, "rating_count": n}."""
    ratings = _ratings_of_ca(ca_profile_id)
    if len(ratings) == 0:
        return {"rating_average": None, "rating_count": 0}
    total = 0
    for rating in ratings:
        total = total + rating.stars
    return {"rating_average": round(total / len(ratings), 1), "rating_count": len(ratings)}


def latest_reviews(ca_profile_id) -> list[dict]:
    """The CA's latest ratings (at most REVIEWS_SHOWN), newest first. Anonymous: no business."""
    reviews = []
    for rating in _ratings_of_ca(ca_profile_id)[:REVIEWS_SHOWN]:
        reviews.append(
            {"stars": rating.stars, "review": rating.review, "created_at": rating.created_at}
        )
    return reviews


# --- Pro-bono queue (MA16) ---------------------------------------------------------------

# Only businesses whose computed MSME tier is one of these may ask for free help.
# A platform policy (docs/DECISIONS.md), not a legal value.
PRO_BONO_TIERS = ["micro"]


def _pro_bono_eligibility(business) -> dict:
    """{"eligible": True/False, "reason": text shown to the business}."""
    tier = onboarding_service.get_msme_tier(business)
    if tier in PRO_BONO_TIERS:
        return {
            "eligible": True,
            "reason": "Your business is a micro enterprise, so you can ask for a free CA.",
        }
    return {
        "eligible": False,
        "reason": "Free (pro-bono) help is for micro enterprises. "
        "Your business profile shows another tier.",
    }


def _queued_request_of(business):
    """The business's request still waiting in the queue, or None."""
    stmt = select(ProBonoRequest).where(
        ProBonoRequest.business_id == business.id,
        ProBonoRequest.status == ProBonoRequestStatus.QUEUED,
    )
    return db.session.scalar(stmt)


def _pro_bono_details(request: ProBonoRequest) -> dict:
    """A pro-bono request as both sides see it."""
    business = onboarding_service.get_business(request.business_id)
    filings = []
    for filing in compliance_service.get_filings_by_ids(request.compliance_item_ids).values():
        filings.append(
            {
                "id": filing.id,
                "form_code": filing.form_code,
                "period_label": filing.period_label,
                "due_date": filing.due_date,
                "blocked_reason": None,
            }
        )
    return {
        "id": request.id,
        "status": request.status,
        "note": request.note,
        "created_at": request.created_at,
        "business_name": business.legal_name,
        "filings": filings,
    }


def _filing_blocked_reason(filing, busy: set):
    """Why a filing cannot be given to a (pro-bono) CA now, or None if it can."""
    if filing.status in FILED_STATUSES:
        return "Already filed."
    if filing.id in busy:
        return "Already requested from a CA or with a CA."
    return None


def get_pro_bono_page(business) -> dict:
    """What the business's pro-bono page shows: eligibility, its queued request, its filings."""
    filings = compliance_service.list_filings(business)
    filing_ids = []
    for filing in filings:
        filing_ids.append(filing.id)
    busy = _busy_filing_ids(filing_ids)

    rows = []
    for filing in filings:
        rows.append(
            {
                "id": filing.id,
                "form_code": filing.form_code,
                "period_label": filing.period_label,
                "due_date": filing.due_date,
                "blocked_reason": _filing_blocked_reason(filing, busy),
            }
        )

    eligibility = _pro_bono_eligibility(business)
    queued = _queued_request_of(business)
    request = None
    if queued is not None:
        request = _pro_bono_details(queued)
    return {
        "eligible": eligibility["eligible"],
        "reason": eligibility["reason"],
        "request": request,
        "filings": rows,
    }


def join_pro_bono_queue(business, filing_ids: list, note: str) -> dict:
    """An eligible business asks for free help with some filings: a `queued` request.

    409 NOT_ELIGIBLE_FOR_PRO_BONO (not micro), 409 PRO_BONO_ALREADY_QUEUED (one at a time),
    404 FILING_NOT_FOUND, 409 FILING_ALREADY_FILED / FILING_ALREADY_REQUESTED.
    """
    if not _pro_bono_eligibility(business)["eligible"]:
        raise ApiError(409, "NOT_ELIGIBLE_FOR_PRO_BONO", "Free help is for micro enterprises only.")
    if _queued_request_of(business) is not None:
        raise ApiError(409, "PRO_BONO_ALREADY_QUEUED", "You are already in the pro-bono queue.")

    # Each filing once, in the order sent.
    unique_ids = []
    for filing_id in filing_ids:
        if filing_id not in unique_ids:
            unique_ids.append(filing_id)

    filings = compliance_service.get_filings_by_ids(unique_ids)
    busy = _busy_filing_ids(unique_ids)
    for filing_id in unique_ids:
        filing = filings.get(filing_id)
        if filing is None or filing.business_id != business.id:
            raise ApiError(404, "FILING_NOT_FOUND", "One of the filings was not found.")
        if filing.status in FILED_STATUSES:
            raise ApiError(409, "FILING_ALREADY_FILED", f"{filing.period_label} is already filed.")
        if filing_id in busy:
            raise ApiError(
                409,
                "FILING_ALREADY_REQUESTED",
                f"{filing.period_label} is already requested from a CA or with a CA.",
            )

    request = ProBonoRequest(
        business_id=business.id, note=note.strip(), compliance_item_ids=unique_ids
    )
    db.session.add(request)
    db.session.commit()
    log.info("Business %s joined the pro-bono queue", business.id)
    return _pro_bono_details(request)


def cancel_pro_bono_request(business, request_id) -> dict:
    """The business leaves the queue (only while `queued`)."""
    request = db.session.get(ProBonoRequest, request_id)
    if request is None or request.business_id != business.id:
        raise ApiError(404, "PRO_BONO_REQUEST_NOT_FOUND", "This request was not found.")
    if request.status != ProBonoRequestStatus.QUEUED:
        raise ApiError(409, "PRO_BONO_NOT_QUEUED", "This request is no longer in the queue.")
    request.status = ProBonoRequestStatus.CANCELLED
    db.session.commit()
    return _pro_bono_details(request)


def _month_start():
    """The start of the current month in Indian time (slots are counted per calendar month)."""
    today = today_in_india()
    return datetime(today.year, today.month, 1, tzinfo=ZoneInfo("Asia/Kolkata"))


def pro_bono_used_this_month(ca_profile_id) -> int:
    """How many pro-bono engagements the CA started this month."""
    stmt = select(Engagement.id).where(
        Engagement.ca_profile_id == ca_profile_id,
        Engagement.is_pro_bono,
        Engagement.activated_at >= _month_start(),
    )
    return len(db.session.scalars(stmt).all())


def get_pro_bono_queue(user: User) -> dict:
    """What the CA's pro-bono page shows: their pledge, slots used, and the queue (oldest first)."""
    ca = get_own_profile(user)
    stmt = (
        select(ProBonoRequest)
        .where(ProBonoRequest.status == ProBonoRequestStatus.QUEUED)
        .order_by(ProBonoRequest.created_at)
    )
    requests = []
    for request in db.session.scalars(stmt):
        requests.append(_pro_bono_details(request))
    return {
        "pledged": ca.pro_bono_slots_per_month,
        "used_this_month": pro_bono_used_this_month(ca.id),
        "verified": ca.verification_status == CaVerificationStatus.VERIFIED,
        "requests": requests,
    }


def _catalog_service_for(filing, itr_service_code):
    """The catalog service that fits a filing (for ITR: the business's ITR form), or None."""
    stmt = (
        select(CatalogService)
        .where(CatalogService.form_code == filing.form_code, CatalogService.is_active)
        .order_by(CatalogService.sort_order)
    )
    for service in db.session.scalars(stmt):
        if _fits(service, filing, itr_service_code):
            return service
    return None


def accept_pro_bono_request(user: User, request_id) -> dict:
    """A verified CA with a free slot takes a queued request: an `active` engagement at ₹0.

    409 CA_NOT_VERIFIED, 409 NO_PRO_BONO_SLOTS, 404 PRO_BONO_REQUEST_NOT_FOUND,
    409 PRO_BONO_NOT_QUEUED (another CA was quicker, or it was cancelled),
    409 FILING_ALREADY_REQUESTED (a filing went to another CA meanwhile).
    """
    ca = get_own_profile(user)
    if ca.verification_status != CaVerificationStatus.VERIFIED:
        raise ApiError(409, "CA_NOT_VERIFIED", "Only verified CAs can take pro-bono requests.")
    if pro_bono_used_this_month(ca.id) >= ca.pro_bono_slots_per_month:
        raise ApiError(409, "NO_PRO_BONO_SLOTS", "You have no free pro-bono slots left this month.")

    # Lock the request, so two CAs cannot take it at the same moment.
    request = db.session.get(ProBonoRequest, request_id, with_for_update=True)
    if request is None:
        raise ApiError(404, "PRO_BONO_REQUEST_NOT_FOUND", "This request was not found.")
    if request.status != ProBonoRequestStatus.QUEUED:
        raise ApiError(409, "PRO_BONO_NOT_QUEUED", "This request is no longer in the queue.")

    business = onboarding_service.get_business(request.business_id)
    filings = compliance_service.get_filings_by_ids(request.compliance_item_ids, lock=True)
    busy = _busy_filing_ids(request.compliance_item_ids)
    for filing_id in request.compliance_item_ids:
        filing = filings.get(filing_id)
        if filing is None or _filing_blocked_reason(filing, busy) is not None:
            raise ApiError(
                409,
                "FILING_ALREADY_REQUESTED",
                "A filing of this request is already filed or with another CA.",
            )

    now = utcnow()
    engagement = Engagement(
        business_id=business.id,
        ca_profile_id=ca.id,
        status=EngagementStatus.REQUESTED,
        is_pro_bono=True,
        requested_at=request.created_at,
        responded_at=now,
    )
    db.session.add(engagement)
    db.session.flush()  # gives engagement.id

    itr_service_code = _itr_service_code(business)
    items = []
    for filing_id in request.compliance_item_ids:
        service = _catalog_service_for(filings[filing_id], itr_service_code)
        if service is None:
            raise ApiError(
                400, "SERVICE_NOT_OFFERED", "No catalog service fits one of the filings."
            )
        item = EngagementItem(
            engagement_id=engagement.id,
            compliance_item_id=filing_id,
            service_id=service.id,
            listed_price=0,
            agreed_price=0,
        )
        db.session.add(item)
        items.append(item)

    _activate(engagement, items)  # status active, filings "With CA"
    request.status = ProBonoRequestStatus.MATCHED
    request.engagement_id = engagement.id
    db.session.commit()
    log.info("CA %s took pro-bono request %s", ca.id, request.id)

    _email_business(engagement, "A CA will help you for free", "pro_bono_matched")
    return _engagement_details(engagement)
