"""Business logic for the regulatory monitor (RE1-RE6).

How it works, step by step:
  1. scan_news() (daily worker job, or `flask regulatory scan`): for each enabled news
     source, check robots.txt, download the RSS feed or web page, and save articles we
     have not seen (same URL or same text = skipped).
  2. Keyword filter: an article is looked at only if it names one of our 7 forms AND a
     change word ("due date", "extended", "late fee", ...).
  3. Gemini (app/utils/gemini_client.py) reads such an article and returns the change as
     JSON; we keep only known values. Without Gemini, a simple keyword version is saved.
     The change is saved as "pending": nobody is told anything yet.
  4. An admin approves or rejects it (list_changes, approve_change, reject_change).
  5. On approval: the businesses with an open filing of those forms (and of the right
     GST scheme / entity type / state, if the change says so) get a tray entry and an
     email; their active CAs get a tray entry, and the client's urgency score rises
     (regulatory_points in ca_workspace_service reads active_changes_for()).

Public functions:
  scan_news() -> dict                               RE2 + RE3 (worker job, CLI)
  list_changes(status) -> list[dict]                RE4 (admin)
  approve_change(admin, change_id) -> dict          RE4 + RE5
  reject_change(admin, change_id) -> dict           RE4
  list_sources() / add_source(data) / set_source_enabled(source_id, enabled)   RE1
  active_changes_for(business_id, today=None) -> list[RegulatoryChange]        urgency hook

Only public news is read; the articles hold no personal data. Only standard-library
tools are used for the web (urllib, urllib.robotparser, xml.etree).
"""

import hashlib
import html
import json
import logging
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from sqlalchemy import func, select

from app.errors import ApiError
from app.extensions import db
from app.models import NewsArticle, NewsSource, RegulatoryChange, RegulatoryChangeMatch, User
from app.models.alerts import NotificationType
from app.models.base import today_in_india, utcnow
from app.models.enums import FormCode
from app.models.onboarding import EntityType, GstScheme
from app.models.regulatory import ChangeType, NewsSourceKind, RegulatoryChangeStatus
from app.services import (
    alerts_service,
    auth_service,
    compliance_service,
    marketplace_service,
    onboarding_service,
)
from app.utils import gemini_client
from app.utils.gstin import GST_STATES

log = logging.getLogger(__name__)

# How we introduce ourselves to websites (robots.txt rules are checked for this name).
USER_AGENT = "CAHelperBot/1.0 (student project; reads public tax news once a day)"
DOWNLOAD_TIMEOUT_SECONDS = 15
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_ITEMS_PER_SOURCE = 30  # newest items of a feed or links of a page, per run
MAX_EXTRACTIONS_PER_RUN = 10  # articles sent to Gemini per run (keeps the quota safe)
RECENT_DAYS = 30  # an approved change raises the CA's urgency for this many days

# Words that suggest a change to a deadline or rule (step 2).
CHANGE_WORDS = [
    "due date",
    "last date",
    "extend",
    "extension",
    "deadline",
    "late fee",
    "waive",
    "waiver",
    "postpone",
]

# How each of our 7 forms is written in news text (step 2).
FORM_PATTERNS = [
    (FormCode.GSTR_1, re.compile(r"\bgstr[- ]?1\b")),
    (FormCode.GSTR_3B, re.compile(r"\bgstr[- ]?3b\b")),
    (FormCode.CMP_08, re.compile(r"\bcmp[- ]?08\b")),
    (FormCode.GSTR_4, re.compile(r"\bgstr[- ]?4\b")),
    (FormCode.TDS_24Q, re.compile(r"\b24q\b")),
    (FormCode.TDS_26Q, re.compile(r"\b26q\b")),
    (FormCode.ITR, re.compile(r"\bitrs?\b|income[- ]tax returns?")),
]

# Short names for messages, e.g. "GSTR-3B".
FORM_NAMES = {
    FormCode.ITR: "ITR",
    FormCode.GSTR_1: "GSTR-1",
    FormCode.GSTR_3B: "GSTR-3B",
    FormCode.CMP_08: "CMP-08",
    FormCode.GSTR_4: "GSTR-4",
    FormCode.TDS_24Q: "24Q",
    FormCode.TDS_26Q: "26Q",
}


# ---------------------------------------------------------------------------------
# Step 1: downloading, robots.txt and reading feeds / pages
# ---------------------------------------------------------------------------------


def _download(url: str) -> tuple[int, str]:
    """Download `url`: (HTTP status, text). Status 0 when the site cannot be reached.

    Kept separate so tests can replace it (tests never use the network).
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_DOWNLOAD_BYTES)
            return response.status, data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        log.warning("Could not download %s: %s", url, type(error).__name__)
        return 0, ""


def _allowed_by_robots(url: str) -> bool:
    """May we fetch `url`? Reads the site's robots.txt (no robots.txt = allowed;
    an error or a refusal to show it = not allowed, to be safe)."""
    parts = urlparse(url)
    status, text = _download(f"{parts.scheme}://{parts.netloc}/robots.txt")
    if status in (404, 410):
        return True
    if status != 200:
        return False
    rules = RobotFileParser()
    rules.parse(text.splitlines())
    return rules.can_fetch(USER_AGENT, url)


def _plain_text(markup: str) -> str:
    """HTML to plain text: tags removed, entities like &amp; decoded, spaces tidied."""
    text = re.sub(r"<[^>]+>", " ", markup)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _read_rss(text: str) -> list[dict]:
    """The items of an RSS feed: [{url, title, content, published_at}], newest first."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        log.warning("A news feed is not valid XML")
        return []
    items = []
    for item in root.iter("item"):
        url = (item.findtext("link") or "").strip()
        title = _plain_text(item.findtext("title") or "")
        if not url or not title:
            continue
        published_at = None
        if item.findtext("pubDate"):
            try:
                published_at = parsedate_to_datetime(item.findtext("pubDate"))
            except (TypeError, ValueError):
                published_at = None
        content = _plain_text(item.findtext("description") or "")
        items.append({"url": url, "title": title, "content": content, "published_at": published_at})
        if len(items) == MAX_ITEMS_PER_SOURCE:
            break
    return items


LINK_PATTERN = re.compile(r"<a\s[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)


def _read_page(page_url: str, text: str) -> list[dict]:
    """The links of an official update page, each as an item: [{url, title, content}].
    Only links whose text is a sentence (8+ words) are kept; menus are skipped."""
    items = []
    seen = set()
    for href, label in LINK_PATTERN.findall(text):
        title = _plain_text(label)
        if len(title.split()) < 8:
            continue
        url = urljoin(page_url, href.strip())
        if url in seen:
            continue
        seen.add(url)
        items.append({"url": url, "title": title[:500], "content": title, "published_at": None})
        if len(items) == MAX_ITEMS_PER_SOURCE:
            break
    return items


def _save_new_articles(source: NewsSource, items: list[dict]) -> list[NewsArticle]:
    """Add the items we have not stored yet (same URL or same text = skipped)."""
    new_articles = []
    for item in items:
        content = item["content"] or item["title"]
        content_hash = hashlib.sha256((item["title"] + "\n" + content).encode("utf-8")).hexdigest()
        known = db.session.scalar(
            select(NewsArticle.id).where(
                (NewsArticle.url == item["url"][:1000]) | (NewsArticle.content_hash == content_hash)
            )
        )
        if known:
            continue
        article = NewsArticle(
            source_id=source.id,
            url=item["url"][:1000],
            title=item["title"][:500],
            published_at=item["published_at"],
            content=content,
            content_hash=content_hash,
        )
        db.session.add(article)
        db.session.flush()  # the next item may repeat this one's text
        new_articles.append(article)
    return new_articles


# ---------------------------------------------------------------------------------
# Steps 2 and 3: keyword filter and extraction
# ---------------------------------------------------------------------------------


def _forms_mentioned(text: str) -> list[str]:
    """The form codes named in `text`, e.g. ["gstr_3b"]."""
    lower = text.lower()
    forms = []
    for code, pattern in FORM_PATTERNS:
        if pattern.search(lower):
            forms.append(code.value)
    return forms


def _looks_relevant(text: str) -> bool:
    """Step 2: does the text name one of our forms AND a change word?"""
    if not _forms_mentioned(text):
        return False
    lower = text.lower()
    found = False
    for word in CHANGE_WORDS:
        if word in lower:
            found = True
    return found


def _extraction_prompt(article: NewsArticle) -> str:
    forms = []
    for code in FormCode:
        forms.append(code.value)
    schemes = []
    for scheme in GstScheme:
        schemes.append(scheme.value)
    entities = []
    for entity in EntityType:
        entities.append(entity.value)
    return (
        "You read Indian tax news for small businesses. Does this article announce a change "
        "to a filing deadline or filing rule?\n\n"
        f"Title: {article.title}\n"
        f"Text: {article.content[:4000]}\n\n"
        "Reply with JSON only, in this shape:\n"
        '{"relevant": true or false,\n'
        ' "change_type": "due_date_extension" | "rate_change" | "new_rule" | "other",\n'
        ' "summary": "one or two plain sentences for a small business owner",\n'
        f' "form_codes": [any of {", ".join(forms)}],\n'
        f' "gst_schemes": [any of {", ".join(schemes)}; empty if all],\n'
        f' "entity_types": [any of {", ".join(entities)}; empty if all],\n'
        ' "states": [Indian state names; empty if all states],\n'
        ' "old_due_date": "YYYY-MM-DD" or null, "new_due_date": "YYYY-MM-DD" or null,\n'
        ' "period": "the return period it is about, e.g. September 2026" or null}\n'
        "Use only facts written in the article; never guess a date."
    )


def _only_known(values, allowed: list[str]) -> list[str]:
    """The items of `values` that are in `allowed` (anything else from Gemini is dropped)."""
    kept = []
    if not isinstance(values, list):
        return kept
    for value in values:
        if isinstance(value, str) and value in allowed and value not in kept:
            kept.append(value)
    return kept


def _date_text(value) -> str | None:
    """A valid YYYY-MM-DD date as text, else None."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _change_from_ai(article: NewsArticle, reply: str) -> dict | None:
    """Gemini's JSON reply as the values of a RegulatoryChange, or None if the article
    is not about a change. Unknown codes and bad dates are dropped (never trusted)."""
    try:
        data = json.loads(reply)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("relevant") is not True:
        return None

    form_values = []
    for code in FormCode:
        form_values.append(code.value)
    form_codes = _only_known(data.get("form_codes"), form_values)
    if not form_codes:
        form_codes = _forms_mentioned(article.title + " " + article.content)
    if not form_codes:
        return None  # no form of ours: nobody to tell

    change_values = []
    for change_type in ChangeType:
        change_values.append(change_type.value)
    change_type = data.get("change_type")
    if change_type not in change_values:
        change_type = ChangeType.OTHER.value

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = article.title
    return {
        "change_type": change_type,
        "summary": summary.strip()[:1000],
        "form_codes": form_codes,
        "affected_categories": _affected(data, "ai"),
        "dates": _dates(data),
    }


def _affected(data: dict, extracted_by: str) -> dict:
    """Who the change is for; an empty or missing list means "everyone"."""
    schemes = []
    for scheme in GstScheme:
        schemes.append(scheme.value)
    entities = []
    for entity in EntityType:
        entities.append(entity.value)
    states = []
    for state in GST_STATES:
        states.append(state["name"])

    affected = {"extracted_by": extracted_by}
    for key, allowed in (
        ("gst_schemes", schemes),
        ("entity_types", entities),
        ("states", states),
    ):
        kept = _only_known(data.get(key), allowed)
        if kept:
            affected[key] = kept
    return affected


def _dates(data: dict) -> dict:
    dates = {}
    for key in ("old_due_date", "new_due_date"):
        value = _date_text(data.get(key))
        if value:
            dates[key] = value
    period = data.get("period")
    if isinstance(period, str) and period.strip():
        dates["period"] = period.strip()[:50]
    return dates


def _change_from_keywords(article: NewsArticle) -> dict:
    """Without Gemini: the article's title as the summary and the forms it names.
    The admin reads the article before approving."""
    text = article.title + " " + article.content
    change_type = ChangeType.OTHER.value
    # Only a done deal counts: "due date extended", not "request for extension".
    if re.search(r"\bextend(ed|s)\b", text.lower()):
        change_type = ChangeType.DUE_DATE_EXTENSION.value
    return {
        "change_type": change_type,
        "summary": article.title,
        "form_codes": _forms_mentioned(text),
        "affected_categories": {"extracted_by": "keywords"},
        "dates": {},
    }


def _extract_change(article: NewsArticle) -> dict | None:
    """Step 3: the change in `article` (Gemini first, keywords if Gemini is unavailable)."""
    if gemini_client.gemini_available():
        try:
            reply = gemini_client.ask_gemini(_extraction_prompt(article), want_json=True)
            if reply.strip().startswith("{"):
                return _change_from_ai(article, reply)  # may be None: not a change
        except ApiError:
            log.info("Gemini unavailable; saving a keyword-based change instead")
    return _change_from_keywords(article)


# ---------------------------------------------------------------------------------
# The job: steps 1-3 for every enabled source (RE2, RE3, RE6)
# ---------------------------------------------------------------------------------


def scan_news() -> dict:
    """Fetch every enabled source, save new articles and the changes found in them.

    Returns counts: {sources, blocked_by_robots, failed, new_articles, changes}.
    Commits once at the end.
    """
    counts = {"sources": 0, "blocked_by_robots": 0, "failed": 0, "new_articles": 0, "changes": 0}
    sources = db.session.scalars(
        select(NewsSource).where(NewsSource.enabled.is_(True)).order_by(NewsSource.name)
    )
    extractions_left = MAX_EXTRACTIONS_PER_RUN
    for source in sources:
        counts["sources"] += 1
        if not _allowed_by_robots(source.url):
            log.warning("robots.txt does not allow %s; skipped", source.url)
            counts["blocked_by_robots"] += 1
            continue
        status, text = _download(source.url)
        if status != 200:
            log.warning("News source %s answered %s; skipped", source.name, status)
            counts["failed"] += 1
            continue

        if source.kind == NewsSourceKind.RSS:
            items = _read_rss(text)
        else:
            items = _read_page(source.url, text)
        new_articles = _save_new_articles(source, items)
        counts["new_articles"] += len(new_articles)

        for article in new_articles:
            if extractions_left == 0:
                break
            if not _looks_relevant(article.title + " " + article.content):
                continue
            extractions_left -= 1
            values = _extract_change(article)
            if values is None or not values["form_codes"]:
                continue
            db.session.add(RegulatoryChange(article_id=article.id, **values))
            counts["changes"] += 1

    db.session.commit()
    log.info("News scan: %s", counts)
    return counts


# ---------------------------------------------------------------------------------
# Admin review and notifying the affected businesses (RE4, RE5)
# ---------------------------------------------------------------------------------


def _change_row(change: RegulatoryChange) -> dict:
    """A change with its article and source, for the admin page."""
    article = db.session.get(NewsArticle, change.article_id)
    source = db.session.get(NewsSource, article.source_id)
    match_count = db.session.scalar(
        select(func.count(RegulatoryChangeMatch.id)).where(
            RegulatoryChangeMatch.change_id == change.id
        )
    )
    return {
        "id": change.id,
        "change_type": change.change_type,
        "summary": change.summary,
        "form_codes": change.form_codes,
        "affected_categories": change.affected_categories,
        "dates": change.dates,
        "status": change.status,
        "created_at": change.created_at,
        "reviewed_at": change.reviewed_at,
        "article_title": article.title,
        "article_url": article.url,
        "published_at": article.published_at,
        "source_name": source.name,
        "match_count": match_count,
    }


def list_changes(status: str | None = None) -> list[dict]:
    """Changes with their article, newest first (at most 100); `status` filters."""
    stmt = select(RegulatoryChange).order_by(RegulatoryChange.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(RegulatoryChange.status == RegulatoryChangeStatus(status))
    rows = []
    for change in db.session.scalars(stmt):
        rows.append(_change_row(change))
    return rows


def _pending_change(change_id) -> RegulatoryChange:
    change = db.session.get(RegulatoryChange, change_id)
    if change is None:
        raise ApiError(404, "CHANGE_NOT_FOUND", "This change does not exist.")
    if change.status != RegulatoryChangeStatus.PENDING:
        raise ApiError(409, "CHANGE_NOT_PENDING", "This change was already reviewed.")
    return change


def _fits(values: list[str] | None, value: str) -> bool:
    """No list (or an empty one) means everyone fits."""
    if not values:
        return True
    return value in values


def _affected_businesses(change: RegulatoryChange) -> list[dict]:
    """The live businesses with an open filing of the change's forms that fit its
    categories (GST scheme, entity type, state)."""
    business_ids = compliance_service.business_ids_with_open_filings(change.form_codes)
    affected = change.affected_categories
    matches = []
    for business in onboarding_service.business_categories(business_ids):
        if not _fits(affected.get("gst_schemes"), business["gst_scheme"]):
            continue
        if not _fits(affected.get("entity_types"), business["entity_type"]):
            continue
        if not _fits(affected.get("states"), business["state"]):
            continue
        matches.append(business)
    return matches


def forms_text(form_codes: list[str]) -> str:
    names = []
    for code in form_codes:
        names.append(FORM_NAMES[FormCode(code)])
    return ", ".join(names)


def approve_change(admin: User, change_id) -> dict:
    """Approve a pending change and tell every affected business (tray + email) and
    their active CAs (tray). Commits once; the emails go out after the commit."""
    change = _pending_change(change_id)
    change.status = RegulatoryChangeStatus.APPROVED
    change.reviewed_at = utcnow()
    change.reviewed_by_id = admin.id

    title = f"Regulatory update: {forms_text(change.form_codes)}"
    body = change.summary
    if change.dates.get("new_due_date"):
        body += f" New due date: {change.dates['new_due_date']}."
    body += " Please check the details with your CA before acting."

    for business in _affected_businesses(change):
        db.session.add(
            RegulatoryChangeMatch(
                change_id=change.id, business_id=business["id"], notified_at=utcnow()
            )
        )
        owner = auth_service.get_active_user(str(business["user_id"]))
        if owner is not None:
            alerts_service.notify(
                owner,
                NotificationType.REGULATORY_UPDATE,
                title,
                body,
                link="/business/compliance",
                email=True,
            )
        for ca_user in marketplace_service.active_cas_of_business(business["id"]).values():
            alerts_service.notify(
                ca_user,
                NotificationType.REGULATORY_UPDATE,
                f"{business['legal_name']}: {title}",
                body,
                link=f"/ca/clients/{business['id']}",
            )

    db.session.commit()
    log.info("Regulatory change %s approved by %s", change.id, admin.id)
    return _change_row(change)


def reject_change(admin: User, change_id) -> dict:
    """Reject a pending change: nobody is told."""
    change = _pending_change(change_id)
    change.status = RegulatoryChangeStatus.REJECTED
    change.reviewed_at = utcnow()
    change.reviewed_by_id = admin.id
    db.session.commit()
    log.info("Regulatory change %s rejected by %s", change.id, admin.id)
    return _change_row(change)


def active_changes_for(business_id, today: date | None = None) -> list[RegulatoryChange]:
    """Approved changes that affected this business in the last RECENT_DAYS days
    (ca_workspace adds urgency points for each)."""
    today = today or today_in_india()
    since = today - timedelta(days=RECENT_DAYS)
    stmt = (
        select(RegulatoryChange)
        .join(RegulatoryChangeMatch, RegulatoryChangeMatch.change_id == RegulatoryChange.id)
        .where(
            RegulatoryChangeMatch.business_id == business_id,
            RegulatoryChange.status == RegulatoryChangeStatus.APPROVED,
            RegulatoryChangeMatch.notified_at >= since,
        )
        .order_by(RegulatoryChange.reviewed_at.desc())
    )
    return list(db.session.scalars(stmt))


# ---------------------------------------------------------------------------------
# News sources (RE1)
# ---------------------------------------------------------------------------------


def list_sources() -> list[NewsSource]:
    return list(db.session.scalars(select(NewsSource).order_by(NewsSource.name)))


def add_source(data: dict) -> NewsSource:
    """Add a source (409 SOURCE_EXISTS for a URL we already have). It starts enabled."""
    exists = db.session.scalar(select(NewsSource.id).where(NewsSource.url == data["url"]))
    if exists:
        raise ApiError(409, "SOURCE_EXISTS", "This URL is already a news source.")
    source = NewsSource(name=data["name"], url=data["url"], kind=NewsSourceKind(data["kind"]))
    db.session.add(source)
    db.session.commit()
    return source


def set_source_enabled(source_id, enabled: bool) -> NewsSource:
    source = db.session.get(NewsSource, source_id)
    if source is None:
        raise ApiError(404, "SOURCE_NOT_FOUND", "This news source does not exist.")
    source.enabled = enabled
    db.session.commit()
    return source
