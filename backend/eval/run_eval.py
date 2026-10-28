"""Evaluate the matcher on the 30 held-out decisions (past_decisions.csv, split = holdout). Test T18.

Usage (from backend/):  python eval/run_eval.py [--json]
Definitions of (a) top-1 candidate agreement, (b) strict decision agreement and (c) wrongly suggested credit: app/evaluation.py and
docs/quality/eval-report.md. Nothing is tuned on this set; it is only scored.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.evaluation import GATE_TOP1, GATE_WRONG, evaluate_holdout  # noqa: E402
from app.store import load  # noqa: E402


def main() -> int:
    m = evaluate_holdout(load())
    if "--json" in sys.argv:
        print(json.dumps(m, indent=1))
        return 0
    print(f"engine: {m['engine']}   n = {m['n']}")
    print(f"(a) top-1 candidate agreement [GATE]: {m['top1_agreement']:.1%}  (gate >= {GATE_TOP1:.0%}; "
          f"{m['top1_deferrals']} of these were 'Evaluator decides' deferrals)")
    print(f"(b) strict decision agreement:        {m['strict_agreement']:.1%}  (reported, not a gate)")
    print(f"(c) wrongly suggested credit [GATE]:  {m['wrong_credit_rate']:.1%}  (gate <= {GATE_WRONG:.0%})")
    print(f"gates met: {m['gates_met']}")
    print("\nper tier (recorded overlap band):")
    for band, t in sorted(m["by_tier"].items()):
        print(f"  {band:28s} n={t['n']:2d} top1={t['top1']:2d} (deferrals {t['top1_deferrals']:2d}) "
              f"strict={t['strict']:2d} wrong_credit={t['wrong_credit']}")
    print("\nrows:")
    for r in m["rows"]:
        mark = "OK " if r["top1_agree"] else "-- "
        print(f"  {mark}{r['ext_id']:18s} recorded={r['recorded']:26s} suggested={r['suggested']:30s} "
              f"top1={r['top1']} {r['top1_overlap_pct']}% conf={r['confidence_pct']}"
              f"{' STRICT' if r['strict'] else ''}{'  WRONG-CREDIT' if r['wrong_credit'] else ''}")
    return 0 if m["gates_met"] else 1      # exit 1 only if (c) > 2 % or (a) < 80 %


if __name__ == "__main__":
    raise SystemExit(main())
