"""Shared building blocks used by every feature module.

    auth/, permissions.py                     authentication and access control
    db/, security/, email/, notifications/,
    ai/, ocr/, storage/, errors.py, health.py shared infrastructure

Every module depends on this package, so a change here must be called out clearly in the PR.
"""
