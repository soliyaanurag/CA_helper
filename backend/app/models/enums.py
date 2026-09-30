"""Allowed values shared by several models.

Enum columns are plain text columns (String(50)) holding the lowercase value, e.g.
"docs_pending". The allowed values are StrEnums next to their model; request checks use
them. Display text lives in the frontend label map (frontend/src/lib/labels.js).
"""

from enum import StrEnum


class UserRole(StrEnum):
    """Who a login account belongs to; also the `role` claim in the JWT."""

    BUSINESS = "business"
    CA = "ca"
    ADMIN = "admin"


class FormCode(StrEnum):
    """The seven filings tracked in v1. Used by compliance, alerts, marketplace and
    regulatory tables; content lives in content/forms/<FORM>/."""

    ITR = "itr"
    GSTR_1 = "gstr_1"
    GSTR_3B = "gstr_3b"
    CMP_08 = "cmp_08"
    GSTR_4 = "gstr_4"
    TDS_24Q = "tds_24q"
    TDS_26Q = "tds_26q"
