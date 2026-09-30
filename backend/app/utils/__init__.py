"""Shared helpers used by routes and services.

decorators.py    roles_required / login_required / current_user (access control)
email.py         send_email(): plain-text email from app/templates/email/
encryption.py    EncryptedString: Fernet-encrypted text columns (PAN, GSTIN, TAN, phone)
storage.py       check_file(): the type and size checks of an upload
gstin.py         the GST state list and GSTIN checks (check character, state code, PAN)
money.py         format_inr(): amounts in the Indian number format for texts
jwt_handlers.py  JWT user loading and token error responses
passwords.py     argon2 hash_password / verify_password
gemini_client.py ask_gemini(): the only way to call Gemini; removes PII first
ocr.py           extract_text(): the text of a PDF / photo, locally (PyMuPDF + Tesseract)
document_text.py the facts in that text: acknowledgement number, date, form, period,
                 document type; registration values for auto-fill
"""
