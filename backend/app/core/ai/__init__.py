"""Gemini access. Not built yet.

Planned: `gemini_client.py`, the ONLY module allowed to call Gemini.
It regex-scrubs PAN/GSTIN/email/phone/Aadhaar-like patterns from every prompt
and logs a warning when it finds one. Model names come from GEMINI_MODEL and
GEMINI_EMBED_MODEL. Never send names, addresses or document contents.
"""
