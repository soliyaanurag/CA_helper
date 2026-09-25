"""Database foundations.

Now:     base.py, the declarative Base with deterministic constraint names.
Planned: shared mixins (UTC created_at/updated_at, soft delete via
         is_active/deleted_at) and money helpers (Decimal, Numeric(12, 2) rupees).
"""
