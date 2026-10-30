"""In-app notifications for a student: what happened to their transfer credit, newest first.

Built from what the app already records, so nothing new has to be written when something happens:
- transcript received (store.transcripts)
- syllabus needed, and each reminder (audit "syllabus_request")
- syllabus received for one of their courses (syllabi[].uploaded_at, set by an upload through the app)
- a decision on one of their courses (audit "decision"; only if it applies to them: reusable, or made for them,
  and not already posted for them)
- credit posted to their BU record (audit "posting"; a decision granting credit posts straight away)

Shown in the app even when the email failed or no mail service is configured: the app is the reliable channel.
Never shown: staff email lists, evaluator names or notes, other students. Read state is one time per student
(Store.notification_seen, PostgreSQL notification_reads): everything at or before it is read.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from typing import Optional

from .store import Store

MAX_ITEMS = 50
_ORDER = ["transcript", "syllabus_request", "syllabus_reminder", "syllabus_received", "decision", "posted"]
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _when(at: Optional[str]) -> dt.datetime:
    """ISO strings from Python and PostgreSQL differ (microseconds, offsets): compare real times."""
    try:
        t = dt.datetime.fromisoformat(at) if at else _EPOCH
    except ValueError:
        return _EPOCH
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _item(kind: str, title: str, body: str, at: str, ext_id: Optional[str] = None) -> dict:
    nid = hashlib.sha256(f"{kind}|{ext_id}|{at}".encode()).hexdigest()[:16]
    return dict(id=nid, kind=kind, title=title, body=body, at=at, ext_id=ext_id)


def for_student(store: Store, student_id: str) -> dict:
    lines = store.lines_for(student_id)
    label = {ln.ext_id: f"{ln.school_code} {ln.course_code}" for ln in lines}
    schools = {s.school_code: s.name for s in store.schools.values()}
    decisions = {d.decision_id: d for d in store.decisions}
    # A decision posts straight away: its "posted" item says it all, so the decision item would repeat it.
    posted_decisions = {(e.get("after") or {}).get("decision_id") for e in store.audit_log
                        if e.get("action") == "posting" and (e.get("after") or {}).get("student_id") == student_id}
    items: list[dict] = []

    for t in store.transcripts:
        if t.student_id == student_id:
            items.append(_item("transcript", "Transcript received",
                               f"Your {schools.get(t.school_code, t.school_code)} transcript was read: {t.course_count} "
                               f"course{'s' if t.course_count != 1 else ''} evaluated.", t.uploaded_at))

    for ext_id, name in label.items():
        rec = store.syllabi.get(ext_id)
        if rec and rec.uploaded_at:
            body = ("An evaluator will now compare it with BU courses." if rec.state == "complete" else
                    "It is missing learning outcomes or a weekly schedule, so an evaluator cannot compare it yet.")
            items.append(_item("syllabus_received", f"Syllabus received for {name}", body, rec.uploaded_at, ext_id))

    for e in store.audit_log:
        a, ext_id, at = e.get("after") or {}, e.get("ext_id"), e.get("at")
        action = e.get("action")
        if action == "syllabus_request" and a.get("student_id") == student_id and ext_id in label:
            reminder = bool(a.get("reminder"))
            need = "a complete syllabus (with learning outcomes and a weekly schedule)" if a.get("need") == "complete" \
                else "the syllabus"
            body = f"Please upload {need} for {label[ext_id]} on your status page. Until it arrives the course stays pending."
            if a.get("status") == "sent" and a.get("emailed_student"):
                body += " We also emailed you."
            items.append(_item("syllabus_reminder" if reminder else "syllabus_request",
                               f"{'Reminder: s' if reminder else 'S'}yllabus needed for {label[ext_id]}", body, at, ext_id))
        elif action == "decision" and ext_id in label:
            d = decisions.get(a.get("decision_id"))
            if d is None or not (d.reusable or student_id in (d.applies_to or [])) or d.decision_id in posted_decisions:
                continue
            outcome = {"Equivalent": f"It transfers as {d.bu_course}.",
                       "Elective": f"It transfers as elective credit ({d.bu_course}).",
                       "No credit": "It does not transfer (no credit)."}.get(d.decision, d.decision)
            follow = "" if d.decision == "No credit" else " The Registrar posts it to your BU record next."
            items.append(_item("decision", f"Decision on {label[ext_id]}", outcome + follow, at, ext_id))
        elif action == "posting" and a.get("student_id") == student_id and ext_id in label:
            units = a.get("units")
            items.append(_item("posted", f"Credit posted for {label[ext_id]}",
                               f"{a.get('bu_course')}" + (f", {units:g} units," if isinstance(units, (int, float)) else "")
                               + " is now on your BU record.", at, ext_id))

    # Same moment (a transcript and its syllabus request): the order things happen in, newest first.
    items.sort(key=lambda i: (_when(i["at"]), _ORDER.index(i["kind"])), reverse=True)
    items = items[:MAX_ITEMS]
    seen = store.notification_seen.get(student_id)
    for i in items:
        i["unread"] = not seen or _when(i["at"]) > _when(seen)
    return dict(items=items, unread=sum(i["unread"] for i in items), seen_at=seen)
