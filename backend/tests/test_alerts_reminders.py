"""The daily reminder job (alerts_service.send_reminders, AL2).

The `business_with_filings` QRMP business registered on 27 Sep 2026: its GSTR-1 for Q2
2026-27 is due on 13 Oct 2026 and GSTR-3B on 22 Oct 2026; Q1 was due in July (before it
registered). The job runs on chosen dates.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import (
    CaProfile,
    CatalogService,
    ComplianceItem,
    Engagement,
    EngagementItem,
    Notification,
    NotificationSetting,
    ReminderLog,
    User,
)
from app.models.alerts import NotificationType
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.seed import seed_service_catalog
from app.services.alerts_service import reminder_kind, send_reminders
from worker import build_scheduler


@pytest.fixture()
def business(business_with_filings, database):
    """The QRMP business, registered on 27 Sep 2026."""
    business_with_filings.created_at = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)
    database.session.commit()
    return business_with_filings


def filing(database, form_code, period_label) -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
    )


def tray_titles(database, user_id) -> list:
    rows = database.session.query(Notification).filter_by(user_id=user_id)
    return sorted(note.title for note in rows)


@pytest.mark.parametrize(
    "days_left, kind",
    [
        (8, None),
        (7, "t_minus_7"),
        (4, "t_minus_7"),
        (3, "t_minus_3"),
        (2, "t_minus_3"),
        (1, "t_minus_1"),
        (0, "t_minus_1"),
        (-1, "overdue"),
        (-40, "overdue"),
    ],
)
def test_reminder_windows(days_left, kind):
    assert reminder_kind(days_left) == kind


def test_seven_days_before_the_owner_gets_a_tray_entry_and_an_email(business, database, mailbox):
    count = send_reminders(date(2026, 10, 6))

    assert count == 1
    owner = database.session.get(User, business.user_id)
    note = database.session.query(Notification).one()
    assert (note.user_id, note.type, note.title) == (
        owner.id,
        NotificationType.DEADLINE_REMINDER,
        "GSTR-1 (Q2 2026-27) is due in 7 days",
    )
    assert note.link == f"/business/compliance/{filing(database, 'gstr_1', 'Q2 2026-27').id}"
    assert len(mailbox) == 1
    assert mailbox[0]["To"] == owner.email
    assert mailbox[0]["Subject"] == "GSTR-1 (Q2 2026-27) is due in 7 days"
    assert "Due on 13 Oct 2026." in mailbox[0].get_content()


def test_each_reminder_is_sent_once(business, database, mailbox):
    send_reminders(date(2026, 10, 6))
    mailbox.clear()

    assert send_reminders(date(2026, 10, 6)) == 0  # the same day again
    assert send_reminders(date(2026, 10, 7)) == 0  # still the T-7 window
    assert mailbox == []
    assert database.session.query(ReminderLog).count() == 1


def test_a_missed_day_is_caught_up_but_earlier_windows_are_not_sent(business, database):
    # The worker did not run 7 or 6 days before: the T-7 reminder goes out 5 days before.
    send_reminders(date(2026, 10, 8))
    # It then skips straight to 1 day before: only T-1, never the missed T-3.
    send_reminders(date(2026, 10, 12))

    kinds = sorted(row.kind for row in database.session.query(ReminderLog))
    assert kinds == ["t_minus_1", "t_minus_7"]


def test_one_summary_email_for_several_reminders(business, database, mailbox):
    # 19 Oct: GSTR-1 (due 13 Oct) is overdue, GSTR-3B (due 22 Oct) is 3 days away.
    count = send_reminders(date(2026, 10, 19))

    assert count == 2
    owner = database.session.get(User, business.user_id)
    assert tray_titles(database, owner.id) == [
        "GSTR-1 (Q2 2026-27) is overdue",
        "GSTR-3B (Q2 2026-27) is due in 3 days",
    ]
    overdue = database.session.query(Notification).filter_by(type="overdue").one()
    assert overdue.body == "It was due on 13 Oct 2026. File it as soon as you can."
    assert len(mailbox) == 1
    assert mailbox[0]["Subject"] == "2 filings need your attention"
    content = mailbox[0].get_content()
    assert "GSTR-1 (Q2 2026-27) is overdue" in content
    assert "GSTR-3B (Q2 2026-27) is due in 3 days" in content


def test_filings_due_before_registration_get_no_reminder(business, database):
    # 19 Oct: Q1's filings (due in July, before 27 Sep) are late too, but not reminded.
    send_reminders(date(2026, 10, 19))
    reminded = {row.compliance_item_id for row in database.session.query(ReminderLog)}
    assert filing(database, "gstr_1", "Q1 2026-27").id not in reminded

    # Had the business registered in June, Q1 would be reminded as overdue.
    business.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    database.session.commit()
    send_reminders(date(2026, 10, 19))
    reminded = {row.compliance_item_id for row in database.session.query(ReminderLog)}
    assert filing(database, "gstr_1", "Q1 2026-27").id in reminded


def test_filed_filings_get_no_reminder(business, database):
    gstr_1 = filing(database, "gstr_1", "Q2 2026-27")
    gstr_1.status = ComplianceStatus.FILED
    database.session.commit()

    assert send_reminders(date(2026, 10, 6)) == 0


def test_switched_off_emails_still_reach_the_tray(business, database, mailbox):
    owner_id = business.user_id
    database.session.add(
        NotificationSetting(
            user_id=owner_id, type=NotificationType.DEADLINE_REMINDER, email_enabled=False
        )
    )
    database.session.commit()

    send_reminders(date(2026, 10, 19))

    assert len(tray_titles(database, owner_id)) == 2
    # Only the overdue reminder is emailed, as a one-line summary.
    assert len(mailbox) == 1
    assert mailbox[0]["Subject"] == "GSTR-1 (Q2 2026-27) is overdue"
    assert "due in 3 days" not in mailbox[0].get_content()


def test_a_deactivated_owner_gets_nothing(business, database, mailbox):
    owner = database.session.get(User, business.user_id)
    owner.is_active = False
    database.session.commit()

    send_reminders(date(2026, 10, 6))

    assert database.session.query(Notification).count() == 0
    assert mailbox == []


def test_the_ca_of_an_active_engagement_is_reminded_too(business, make_user, database, mailbox):
    seed_service_catalog()
    ca_user = make_user(role=UserRole.CA, full_name="Meera Shah")
    ca = CaProfile(
        user_id=ca_user.id,
        membership_no="123456",
        cop_number="COP-1",
        city="Pune",
        languages=["english"],
        specializations=["gstr_1"],
        capacity=10,
        years_experience=5,
        verification_status=CaVerificationStatus.VERIFIED,
    )
    database.session.add(ca)
    database.session.flush()
    engagement = Engagement(
        business_id=business.id, ca_profile_id=ca.id, status=EngagementStatus.ACTIVE
    )
    database.session.add(engagement)
    database.session.flush()
    gstr_1 = filing(database, "gstr_1", "Q2 2026-27")
    gstr_1.status = ComplianceStatus.WITH_CA
    service = database.session.query(CatalogService).filter_by(code="gstr_1").one()
    database.session.add(
        EngagementItem(
            engagement_id=engagement.id,
            compliance_item_id=gstr_1.id,
            service_id=service.id,
            listed_price=Decimal("600"),
        )
    )
    database.session.commit()

    send_reminders(date(2026, 10, 6))

    assert tray_titles(database, ca_user.id) == [
        "Asha Traders: GSTR-1 (Q2 2026-27) is due in 7 days"
    ]
    ca_note = database.session.query(Notification).filter_by(user_id=ca_user.id).one()
    assert ca_note.link == "/ca/engagements"
    assert sorted(message["To"] for message in mailbox) == sorted(
        [ca_user.email, database.session.get(User, business.user_id).email]
    )
    # The engagement ends: the CA is not reminded of the overdue step.
    engagement.status = EngagementStatus.COMPLETED
    database.session.commit()
    send_reminders(date(2026, 10, 19))
    assert len(tray_titles(database, ca_user.id)) == 1


def test_worker_runs_the_reminders_every_morning(app):
    job = build_scheduler(app).get_job("alerts.reminders")

    assert job is not None
    assert str(job.trigger) == "cron[hour='8', minute='15']"


def test_reminders_run_on_demand_from_the_command_line(app, business):
    result = app.test_cli_runner().invoke(args=["alerts", "send-reminders"])

    assert result.exit_code == 0, result.output
    assert "reminder(s)" in result.output
