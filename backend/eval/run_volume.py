"""Volume test: how the API behaves with a realistic intake (scorecard 4.2, ADR 0007).

Usage (from backend/):  python eval/run_volume.py [--scales 0.1,0.5,1,2] [--sample 200] [--json]

Scale 1 = one year of BU transfer volume from discovery: 800 students x 10 courses = 8,000 transcript lines.
For each scale the in-memory store gets N synthetic students on top of the seed data, then the real API routes are
timed through FastAPI's TestClient:
  - student status page   GET /api/students/{id}/evaluation   (a sample of students; p50 / p95)
  - review queue          GET /api/review-queue                (all departments, and one department)
  - registrar export      GET /api/exports/mybu.csv
PDF reading (pdfplumber) is timed once on the sample transcript PDFs; it does not depend on volume.

Runs offline like the tests (ADR 0003): offline matcher, no database, no Azure. Synthetic data only.
Course mix per line: 65 % catalogue courses of the student's school (existing matches, maybes, ineligible types),
35 % courses new to the catalogue, drawn from a pool of 3 per student (the "mixed schools" case in ADR 0007), so the
matcher does real work and the number of distinct courses grows with volume.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

for _k in ("AZURE_OPENAI_ENDPOINT", "AZURE_DI_ENDPOINT", "AZURE_SEARCH_ENDPOINT", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
           "AZURE_OPENAI_EMBEDDING_ENDPOINT", "AZURE_STORAGE_BLOB_ENDPOINT", "AZURE_COMMUNICATION_ENDPOINT",
           "NOTIFY_WEBHOOK_URL", "POSTGRES_HOST"):
    os.environ.pop(_k, None)
os.environ["TRANSFERIQ_AUTH_MODE"] = "demo"
os.environ["TRANSFERIQ_PREWARM"] = "0"
os.environ["TRANSFERIQ_SYLLABUS_REMINDER_DAYS"] = "0"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402

from app import matcher  # noqa: E402
from app import store as store_mod  # noqa: E402
from app.ingest import parse_transcript  # noqa: E402
from app.main import app  # noqa: E402
from app.store import ExtCourse, Student, TranscriptLine  # noqa: E402

LINES_PER_STUDENT = 10
BASE_STUDENTS = 800
GRADES = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "P"]
GRADE_W = [14, 12, 14, 16, 12, 10, 9, 5, 3, 5]
TERMS = ["Fall 2023", "Spring 2024", "Fall 2024", "Spring 2025"]
SUFFIX = ["Foundations of", "Topics in", "Introduction to", "Advanced", "Principles of", "Seminar in"]


def rss_mb() -> float:
    """Peak resident memory of this process in MB (Windows and Unix), or -1 if unknown."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                   "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                   "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32")
            k32.GetCurrentProcess.restype = wintypes.HANDLE            # pseudo-handle -1: keep it pointer-sized
            k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return -1.0
            return pmc.PeakWorkingSetSize / 2**20
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1.0


def populate(n_students: int, rng: random.Random) -> dict:
    """Add n synthetic students with LINES_PER_STUDENT lines each to the (freshly reset) store."""
    st = store_mod.STORE
    by_school: dict[str, list[ExtCourse]] = {}
    for c in st.ext_courses.values():
        by_school.setdefault(c.school_code, []).append(c)
    schools = sorted(by_school)
    pool: list[ExtCourse] = []
    for i in range(n_students * 3):                  # courses new to the catalogue, as an upload would create them
        base = rng.choice(list(st.ext_courses.values()))
        title = f"{rng.choice(SUFFIX)} {base.title}"
        code = f"LT {1000 + i}"
        pool.append(ExtCourse(f"{base.school_code}|{code}", base.school_code, code, title, base.credits, base.calendar,
                              base.program_area, "Academic", 100 if i % 2 else 200, title, [], []))
    for c in pool:
        st.ext_courses[c.ext_id] = c
    new_lines = []
    for s in range(n_students):
        school = rng.choice(schools)
        sid = f"SYN-L{s:05d}"
        st.students[sid] = Student(sid, f"Load Test {s}", "Undeclared", "Fall 2026", "College of Arts & Sciences",
                                   previous_school=school)
        for _ in range(LINES_PER_STUDENT):
            c = rng.choice(by_school[school]) if rng.random() < 0.65 else rng.choice(pool)
            new_lines.append(TranscriptLine(sid, c.school_code, rng.choice(TERMS), c.ext_id, c.course_code, c.title,
                                            c.credits, c.calendar, rng.choices(GRADES, GRADE_W)[0]))
    st.lines = st.lines + new_lines
    return dict(students=len(st.students), lines=len(st.lines), distinct_courses=len({ln.ext_id for ln in st.lines}))


def timed(fn) -> tuple[float, object]:
    t = time.perf_counter()
    r = fn()
    return time.perf_counter() - t, r


def run_scale(scale: float, sample: int, seed: int) -> dict:
    store_mod.reset()
    matcher.clear_cache()
    rng = random.Random(seed)
    n = max(1, round(BASE_STUDENTS * scale))
    sizes = populate(n, rng)
    client = TestClient(app)
    ids = [f"SYN-L{i:05d}" for i in rng.sample(range(n), min(sample, n))]
    per = []
    for sid in ids:
        dt_s, r = timed(lambda: client.get(f"/api/students/{sid}/evaluation", headers={"X-Demo-Role": "CreditStaff"}))
        assert r.status_code == 200, (sid, r.status_code, r.text[:200])
        per.append(dt_s)
    # First call computes a recommendation for every maybe course not seen yet (cold); the second call is the steady
    # state an evaluator sees on every refresh (recommendations cached, students re-evaluated).
    q_cold_s, r = timed(lambda: client.get("/api/review-queue", headers={"X-Demo-Role": "Evaluator"}))
    assert r.status_code == 200, r.text[:200]
    queue_items = len(r.json())
    q_warm_s, r = timed(lambda: client.get("/api/review-queue", headers={"X-Demo-Role": "Evaluator"}))
    assert r.status_code == 200, r.text[:200]
    q_dept_s, r = timed(lambda: client.get("/api/review-queue", params={"department": "Psychology"},
                                           headers={"X-Demo-Role": "Evaluator"}))
    assert r.status_code == 200, r.text[:200]
    exp_s, r = timed(lambda: client.get("/api/exports/mybu.csv", headers={"X-Demo-Role": "Registrar"}))
    assert r.status_code == 200, r.text[:200]
    per_ms = sorted(x * 1000 for x in per)
    return dict(scale=scale, **sizes, sample=len(per),
                status_p50_ms=round(statistics.median(per_ms), 1),
                status_p95_ms=round(per_ms[max(0, int(len(per_ms) * 0.95) - 1)], 1),
                status_all_students_s=round(statistics.mean(per) * sizes["students"], 1),
                queue_items=queue_items, queue_cold_s=round(q_cold_s, 2), queue_warm_s=round(q_warm_s, 2),
                queue_one_dept_s=round(q_dept_s, 2),
                export_s=round(exp_s, 2), rss_mb=round(rss_mb()))


def pdf_reading() -> dict:
    folder = os.path.join(store_mod.REPO_ROOT, "data", "synthetic", "transcripts")
    times, lines = [], 0
    for f in sorted(os.listdir(folder)):
        if f.endswith(".pdf"):
            with open(os.path.join(folder, f), "rb") as fh:
                data = fh.read()
            dt_s, parsed = timed(lambda: parse_transcript(data))
            times.append(dt_s * 1000)
            lines += len(parsed.lines)
    return dict(files=len(times), lines=lines, mean_ms=round(statistics.mean(times), 1), max_ms=round(max(times), 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scales", default="0.1,0.5,1,2")
    ap.add_argument("--sample", type=int, default=200, help="students timed per scale")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    pdf = pdf_reading()
    rows = []
    for s in (float(x) for x in a.scales.split(",")):
        rows.append(run_scale(s, a.sample, a.seed))
        if not a.json:
            print(f"scale {s:g}: done ({rows[-1]['lines']} lines)", file=sys.stderr)
    if a.json:
        print(json.dumps(dict(pdf=pdf, scales=rows), indent=1))
        return 0
    print(f"engine: {matcher.engine_name()}   PDF reading: {pdf['files']} transcripts, mean {pdf['mean_ms']} ms, "
          f"max {pdf['max_ms']} ms\n")
    print("| Scale | Students | Transcript lines | Distinct courses | Status page p50 / p95 (ms) | "
          "All status pages (s) | Queue items | Review queue first / refresh / one dept (s) | MyBU export (s) | "
          "Peak memory (MB) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['scale']:g}x | {r['students']:,} | {r['lines']:,} | {r['distinct_courses']:,} | "
              f"{r['status_p50_ms']} / {r['status_p95_ms']} | {r['status_all_students_s']} | {r['queue_items']:,} | "
              f"{r['queue_cold_s']} / {r['queue_warm_s']} / {r['queue_one_dept_s']} | {r['export_s']} | "
              f"{r['rss_mb']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
