"""Business logic for the CA marketplace: CA profiles, prices and the list businesses browse.

get_own_profile(user) -> CaProfile                  the CA's profile (404 before the first save)
save_own_profile(user, **fields) -> CaProfile        create or update it
list_verified_cas(page, page_size, ...) -> dict      verified CAs, filtered and paginated
get_verified_ca(profile_id) -> dict                  one verified CA with the services they offer
list_catalog() -> list[dict]                         catalog services with their typical price range
get_own_menu(user) -> dict                           the services the CA offers, with prices
save_own_menu(user, items) -> dict                   replace the CA's price menu

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
from statistics import median

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import CaProfile, CaService, CatalogService, User
from app.models.base import utcnow
from app.models.marketplace import CaVerificationStatus

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


def get_verified_ca(profile_id) -> dict:
    """One listed CA's public details and the services they offer, in catalog order.

    Each service has the CA's price and the typical range, so the page can compare
    them. Raises 404 CA_NOT_FOUND for a CA businesses may not see (not verified, or
    the account is deactivated), exactly like the list.
    """
    stmt = select(CaProfile).join(CaProfile.user).where(CaProfile.id == profile_id)
    stmt = _only_listed_cas(stmt)
    profile = db.session.scalar(stmt)
    if profile is None:
        raise ApiError(404, "CA_NOT_FOUND", "This CA is not listed on the marketplace.")

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
