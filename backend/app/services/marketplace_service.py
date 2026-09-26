"""Business logic for the CA marketplace: CA profiles and the list businesses browse.

get_own_profile(user) -> CaProfile                  the CA's profile (404 before the first save)
save_own_profile(user, **fields) -> CaProfile        create or update it
list_verified_cas(page, page_size, ...) -> dict      verified CAs, filtered and paginated

Verification: a new profile is `pending` until an admin checks it. If a verified or
rejected CA changes the membership or CoP number, it goes back to `pending` (the
admin must check the new number). A rejected CA's profile goes back to `pending`
on any save, so fixing it and saving asks for a new check.
"""

import logging

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import CaProfile, User
from app.models.marketplace import CaVerificationStatus

log = logging.getLogger(__name__)

# Changing one of these needs a new admin check.
IDENTITY_FIELDS = ("membership_no", "cop_number")


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
) -> dict:
    """Verified CAs with live accounts, most experienced first.

    `specialization` / `language` keep CAs whose list contains that code; `city`
    keeps CAs whose city contains the text (any case).
    """
    stmt = (
        select(CaProfile)
        .join(CaProfile.user)
        .where(
            CaProfile.verification_status == CaVerificationStatus.VERIFIED,
            CaProfile.is_active,
            User.is_active,
            User.deleted_at.is_(None),
        )
        .order_by(CaProfile.years_experience.desc(), User.full_name, CaProfile.id)
    )
    if specialization:
        stmt = stmt.where(CaProfile.specializations.contains([specialization]))
    if language:
        stmt = stmt.where(CaProfile.languages.contains([language]))
    if city and city.strip():
        stmt = stmt.where(CaProfile.city.icontains(city.strip(), autoescape=True))

    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    return {"items": result.items, "page": page, "page_size": page_size, "total": result.total}
