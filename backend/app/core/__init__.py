"""Shared building blocks used by every feature module.

Owners (see docs/OWNERSHIP.md):
    auth/, permissions.py                     Member A
    db/, security/, email/, notifications/,
    ai/, ocr/, storage/, errors.py, health.py Member B

Changes here go in a separate small PR labelled `core`, reviewed by the owner.
"""
