"""Matcher quality on the held-out decisions (sponsor gates, test T18).

Three numbers (also in docs/quality/eval-report.md):

(a) top-1 candidate agreement - GATE CLAIM (>= 80 %). Looks only at the matcher's top-ranked BU candidate:
      * recorded Equivalent X -> top-1 candidate is X
      * recorded Elective C   -> top-1 candidate is in C's BU department (e.g. CAS PS 2TR -> any CAS PS course)
    Whether the suggestion was "Equivalent", "Evaluator decides" or "Elective" does not matter here. A deferral only
    counts when its top candidate is the recorded equivalent course (or right department for an elective). The
    deferrals inside (a) are reported separately (`top1_deferrals`).
(b) strict decision agreement - the suggested decision AND code equal the recorded ones exactly ("Equivalent X" or
    "Elective C"). "Evaluator decides" never counts. Reported, not a gate.
(c) wrongly suggested credit - GATE (<= 2 %). The suggestion is "Equivalent X" but the evaluator did not grant
    Equivalent X.

The matcher sees only non-ground-truth fields. Holdout decisions are only scored here; nothing is tuned on them.
"""
from __future__ import annotations

from .matcher import engine_name, recommend_many
from .store import Store

GATE_TOP1 = 0.80
GATE_WRONG = 0.02


def _dept(code: str) -> str:
    parts = (code or "").split()
    return parts[1] if len(parts) > 1 else ""


def _band(pct) -> str:
    if pct is None:
        return "unknown"
    return "equivalent (>=80%)" if pct >= 80 else "evaluator_decides (50-79%)" if pct >= 50 else "elective (<50%)"


def evaluate_holdout(store: Store) -> dict:
    bus = list(store.bu_courses.values())
    rows = []
    recs = recommend_many([(store.ext_courses[d.ext_id], bus, store.syllabi.get(d.ext_id)) for d in store.holdout_decisions])
    for d, rec in zip(store.holdout_decisions, recs):
        sd, sc = rec["suggested_decision"], rec["suggested_code"]
        top = rec["candidates"][0]["bu_code"] if rec["candidates"] else ""
        if d.decision == "Equivalent":
            top1 = top == d.bu_course
        elif d.decision == "Elective":
            top1 = bool(top) and _dept(top) == _dept(d.bu_course)
        else:
            top1 = False
        strict = sd == d.decision and sc == d.bu_course
        wrong_credit = sd == "Equivalent" and not (d.decision == "Equivalent" and sc == d.bu_course)
        rows.append(dict(ext_id=d.ext_id, recorded=f"{d.decision} {d.bu_course}", recorded_overlap_pct=d.overlap_pct,
                         band=_band(d.overlap_pct), suggested=f"{sd} {sc}", top1=top,
                         top1_overlap_pct=rec["candidates"][0]["overlap_pct"] if rec["candidates"] else 0,
                         confidence_pct=rec["confidence_pct"], preliminary=rec["preliminary"],
                         top1_agree=top1, deferral=sd == "Evaluator decides", strict=strict, wrong_credit=wrong_credit))
    n = len(rows)
    by_tier: dict[str, dict] = {}
    for r in rows:
        t = by_tier.setdefault(r["band"], dict(n=0, top1=0, top1_deferrals=0, strict=0, wrong_credit=0))
        t["n"] += 1
        t["top1"] += r["top1_agree"]
        t["top1_deferrals"] += r["top1_agree"] and r["deferral"]
        t["strict"] += r["strict"]
        t["wrong_credit"] += r["wrong_credit"]
    for t in by_tier.values():
        t["top1_agreement"] = round(t["top1"] / t["n"], 4) if t["n"] else 0.0

    def rate(key):
        return round(sum(1 for r in rows if r[key]) / n, 4) if n else 0.0

    top1 = rate("top1_agree")
    wrong = rate("wrong_credit")
    return dict(engine=engine_name(), n=n,
                top1_agreement=top1,                         # (a) gate claim
                top1_deferrals=sum(1 for r in rows if r["top1_agree"] and r["deferral"]),
                deferrals=sum(1 for r in rows if r["deferral"]),   # contract v0.3.0 Metrics.deferrals
                strict_agreement=rate("strict"),             # (b)
                wrong_credit_rate=wrong,                     # (c) gate
                gates_met=bool(n and top1 >= GATE_TOP1 and wrong <= GATE_WRONG),
                by_tier=by_tier, rows=rows)
