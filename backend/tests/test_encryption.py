"""app/utils/encryption.py: EncryptedString keeps PAN, GSTIN, TAN and phone unreadable at rest."""

from decimal import Decimal

import pytest
from sqlalchemy import select, text

from app.models import Business, decrypt, encrypt, EntityType

PAN = "ABCPE1234F"
GSTIN = "27ABCPE1234F1Z5"


@pytest.fixture()
def business(database, make_user):
    row = Business(
        user_id=make_user().id,
        legal_name="Asha Traders",
        entity_type=EntityType.PROPRIETORSHIP,
        state="Maharashtra",
        address="12 MG Road, Pune",
        description="Retail shop",
        annual_turnover=Decimal("2500000.00"),
        investment_amount=Decimal("300000.00"),
        pan=PAN,
        phone="9876543210",
        gst_registered=True,
        gstin=GSTIN,
        deducts_tds=False,
        pays_salary_above_limit=False,
    )
    database.session.add(row)
    database.session.commit()
    return row


def test_values_come_back_as_plain_text(database, business):
    database.session.expire_all()  # force a real read from the database

    loaded = database.session.scalar(select(Business))

    assert loaded.pan == PAN
    assert loaded.gstin == GSTIN
    assert loaded.tan is None  # NULL stays NULL


def test_the_database_never_holds_the_plain_text(database, business):
    raw = database.session.execute(
        text("SELECT pan, gstin, phone FROM businesses WHERE id = :id"), {"id": business.id}
    ).one()

    for column, plain in zip(raw, (PAN, GSTIN, "9876543210"), strict=True):
        assert plain not in column
        assert column.startswith("gAAAAA")  # a Fernet token


def test_the_same_value_encrypts_differently_each_time(app):
    # Why an encrypted column cannot be searched or made UNIQUE (docs/DECISIONS.md).
    assert encrypt(PAN) != encrypt(PAN)
    assert decrypt(encrypt(PAN)) == PAN


def test_a_missing_key_says_how_to_make_one(app, monkeypatch):
    monkeypatch.setitem(app.config, "FIELD_ENCRYPTION_KEY", None)

    with pytest.raises(RuntimeError, match="FIELD_ENCRYPTION_KEY is not set. Generate one"):
        encrypt(PAN)


def test_a_wrong_key_is_reported_clearly(app, monkeypatch):
    token = encrypt(PAN)
    monkeypatch.setitem(
        app.config, "FIELD_ENCRYPTION_KEY", "Q2FIZWxwZXItdGVzdC1rZXktdGhhdC1pcy13cm9uZyE="
    )

    with pytest.raises(RuntimeError, match="not the key it was encrypted with"):
        decrypt(token)
