"""Business logic for the CA marketplace: CA profiles, prices and the list businesses browse.

get_own_profile(user) -> CaProfile                  the CA's profile (404 before the first save)
save_own_profile(user, **fields) -> CaProfile        create or update it
list_verified_cas(page, page_size, ...) -> dict      verified CAs, filtered and paginated
get_verified_ca(profile_id) -> dict                  one verified CA with the services they offer
list_catalog() -> list[dict]                         catalog services with their typical price range
get_own_menu(user) -> dict                           the services the CA offers, with prices
save_own_menu(user, items) -> dict                   replace the CA's price menu

Engagements (a business working with a CA on some filings):
list_requestable_filings(business, ca_id) -> list    the business's filings, with this CA's prices
create_request(business, ca_id, items) -> dict       send a request (status `requested`)
list_business_engagements(business) -> list          the business's engagements, newest first
list_ca_engagements(user) -> list                    the CA's engagements, newest first
accept_request / send_quote / decline_request / complete_engagement(user, id)    CA actions
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

Verification: a new profile is `pending` until an admin checks it. If a verified or
rejected CA changes the membership or CoP number, it goes back to `pending` (the
admin must check the new number). A rejected CA's profile goes back to `pending`
on any save, so fixing it and saving asks for a new check.
"""

import logging
from datetime import timedelta
from statistics import median

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import CaProfile, CaService, CatalogService, Engagement, EngagementItem, User
from app.models.base import utcnow
from app.models.compliance import ComplianceStatus
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.services import compliance_service, onboarding_service
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
    elif profile.verification_status == CaVerificationStatus.REJECTED or any(
        getattr(profile, name) != fields[name] for name in IDENTITY_FIELDS
    ):
        profile.verification_status = CaVerificationStatus.PENDING

    for name, value in fields.items():
        setattr(profile, name, value)
    db.session.commit()
    return profile


def list_verified_cas(
    page: int,
    page_size: int,
    specialization: str | None = None,
    language: str | None = None,
    city: str | None = None,
    service: str | None = None,
) -> dict:
    """Verified CAs with live accounts, most experienced first.

    `specialization` / `language` keep CAs whose list contains that code; `city`
    keeps CAs whose city contains the text (any case); `service` (a catalog code)
    keeps CAs who offer that service, and each item then has their `price`.
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

    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)

    items = []
    for profile in result.items:
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
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": result.total}


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
    }


# --- Engagements: requests, answers and the lifecycle (MA9, MA10, MA11, MA13) --------

# An engagement in one of these still holds its filings: nobody may request them again.
OPEN_STATUSES = [EngagementStatus.REQUESTED, EngagementStatus.QUOTED, EngagementStatus.ACTIVE]

# Filings in these states are done: there is nothing left for a CA to do.
FILED_STATUSES = [ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED]

# A CA has this long to answer a request. (The job that expires old requests is MA12.)
ANSWER_WITHIN = timedelta(hours=48)


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
    filings = compliance_service.list_filings(business)
    filing_ids = []
    for filing in filings:
        filing_ids.append(filing.id)
    busy = _busy_filing_ids(filing_ids)

    result = []
    for filing in filings:
        options = []
        for service, price in services:
            if service.form_code == filing.form_code:
                options.append({"service_id": service.id, "name": service.name, "price": price})

        blocked_reason = None
        if filing.status in FILED_STATUSES:
            blocked_reason = "Already filed."
        elif filing.id in busy:
            blocked_reason = "Already requested from a CA or with a CA."
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
    409 FILING_ALREADY_REQUESTED, 400 SERVICE_NOT_OFFERED.
    """
    ca = _find_listed_ca(ca_profile_id)

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
        if service_id not in offered or offered[service_id][0].form_code != filing.form_code:
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


def accept_request(user: User, engagement_id) -> dict:
    """The CA accepts at the listed prices: status `active`."""
    engagement = _ca_engagement(user, engagement_id)
    _check_status(engagement, EngagementStatus.REQUESTED)
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
