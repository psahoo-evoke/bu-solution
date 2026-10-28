"""TransferIQ synthetic data v2: source institutions = Northeastern (NEU) and NYU, from the hackathon workbook.
Real course codes/titles/credits for the 76 catalog courses; all descriptions, outcomes, students, grades,
syllabi and decisions are synthetic. Two fictional helper schools remain for tests NU/NYU cannot cover
(quarter calendar, non-accredited school). Writes data.json."""
import json, random, os
import pandas as pd
from catalog import BU, PROGRAMS

rng = random.Random(2026)
HERE = os.path.dirname(os.path.abspath(__file__))
WB = os.path.join(HERE, "..", "..", "data", "BU_Transfer_Program_Course_Match.xlsx")

VERBS = ["Explain the core ideas of", "Apply", "Analyze problems involving", "Use", "Evaluate approaches to", "Communicate findings about"]
TAILS = ["", " to solve standard problems", "", " in practical exercises", "", ""]
ACT = {"CS": "programming assignments", "EC": "data and policy exercises", "PS": "readings and short research reports",
       "BI": "weekly laboratory sessions", "CH": "weekly laboratory sessions", "MA": "problem sets and proofs"}
def outcomes(t): return [f"{VERBS[i]} {t[i]}{TAILS[i]}" for i in range(6)]
def tcase(s): return " ".join(w if w in ("and","of","in","for","the","to") else w[0].upper()+w[1:] for w in s.split())
def units(cr, cal): return round(cr * 2 / 3, 2) if cal == "Quarter" else float(cr)
def tier(ov): return "Equivalent (>=80%)" if ov >= 0.8 else "Evaluator decides (50-79%)" if ov >= 0.5 else "Elective (<50%)"

# ------------------------------------------------------------------ BU catalog (unchanged from v1)
bu_rows = []
for dept, num, title, req, real, topics in BU:
    t = [x.strip() for x in topics.split(";")]
    lvl = min(num // 100, 3); prog = PROGRAMS[dept]
    desc = (f"{title} is an {'introductory' if lvl==1 else 'intermediate' if lvl==2 else 'advanced'} course in {prog.lower()}. "
            f"It covers {t[0]}, {t[1]}, {t[2]} and {t[3]}, and builds toward {t[4]} and {t[5]}. "
            f"Students work through {ACT[dept]}, with later units on {t[6]} and {t[7]}.")
    res = ""
    if req.startswith("Group C"): res = "CS Group C: must be taken at BU (requirement blocked; units may post as elective)"
    elif dept == "BI" and num > 108: res = "Biology: at least five BI courses beyond BI 107/108 must be taken at BU"
    elif dept == "EC" and num >= 200: res = "Economics: max four 200+ level courses transferred after matriculation"
    bu_rows.append(dict(bu_code=f"CAS {dept} {num}", dept=dept, title=title, program=prog, requirement_type=req, level=lvl*100,
                        credits=4, residency_rule=res,
                        source=("Code/title from provided BU workbook (public catalog); description synthetic" if real else "Fully synthetic course (not a real BU offering)"),
                        description=desc, learning_outcomes=outcomes(t), topics=t))
BU_BY = {r["bu_code"]: r for r in bu_rows}
POOL = {}
for r in bu_rows: POOL.setdefault(r["program"], set()).update(r["topics"])

# ------------------------------------------------------------------ schools
SCHOOLS = [
 dict(school_code="NEU", name="Northeastern University", type="Private research university (Boston)", calendar="Semester",
      accreditation="Regionally accredited", location="Boston, MA", role="Primary source school (hackathon data)",
      grading="A-F with +/-", note="Real institution. Course codes/titles/credits from its public catalog via the hackathon workbook. Student records, grades and syllabi are synthetic and were NOT issued by Northeastern."),
 dict(school_code="NYU", name="New York University", type="Private research university (New York)", calendar="Semester",
      accreditation="Regionally accredited", location="New York, NY", role="Primary source school (hackathon data)",
      grading="A-F with +/-", note="Real institution. Course codes/titles/credits from its public catalog via the hackathon workbook. Student records, grades and syllabi are synthetic and were NOT issued by NYU."),
 dict(school_code="PSC", name="Pinecrest State College (fictional)", type="Fictional four-year public college", calendar="Quarter",
      accreditation="Regionally accredited", location="Fictional", role="Test helper: quarter-system conversion (NU and NYU use semesters)",
      grading="A-F with +/-", note="Fictional. Used for one summer course only."),
 dict(school_code="SOI", name="Summit Online Institute (fictional)", type="Fictional online institute", calendar="Semester",
      accreditation="Not regionally accredited (national accreditor only)", location="Online", role="Test helper: accreditation rule",
      grading="A-F", note="Fictional. Used for the non-accredited-school test only."),
]
SCH = {s["school_code"]: s for s in SCHOOLS}

ext_rows, BY_CODE = [], {}
def add_row(row):
    row.setdefault("elective_code", None)
    row["ext_id"] = f'{row["school_code"]}|{row["course_code"]}'
    assert row["ext_id"] not in BY_CODE, row["ext_id"]
    ext_rows.append(row); BY_CODE[row["ext_id"]] = row
    return row

def derive(school, bu_code, k, code, title, credits, source, level=None, note=""):
    bu = BU_BY[bu_code]
    shared = rng.sample(bu["topics"], k)
    foreign = rng.sample(sorted(POOL[bu["program"]] - set(bu["topics"])), 8 - k)
    topics = shared + foreign; rng.shuffle(topics)
    cal = SCH[school]["calendar"]
    desc = (f"{title}. Topics include {topics[0]}, {topics[1]}, {topics[2]}, {topics[3]} and {topics[4]}; "
            f"later weeks address {topics[5]}, {topics[6]} and {topics[7]}.")
    return add_row(dict(school_code=school, course_code=code, title=title, credits=credits, calendar=cal,
                        units_if_transferred=units(credits, cal), program_area=bu["program"], course_type="Academic",
                        level=level or bu["level"], source=source, description=desc, learning_outcomes=outcomes(topics),
                        topics=topics, gt_counterpart=bu_code, gt_overlap=round(k/8, 3), gt_tier=tier(k/8), notes=note))

# ------------------------------------------------------------------ real NU / NYU catalog courses (76)
x = pd.read_excel(WB, sheet_name=None)
cm = x["Course Match"].iloc[:41]
RANK = {"Likely equivalent": 3, "Partial - syllabus review": 2, "Must be taken at BU": 1, "No equivalent found": 0}
best = {}
for _, r in cm.iterrows():
    for sc, col, lv in (("NEU", "Northeastern course", "NU match level"), ("NYU", "NYU course", "NYU match level")):
        c = r[col]
        if not isinstance(c, str) or c.strip() in ("—", "-"): continue
        key = (sc, c.strip())
        if key not in best or RANK[r[lv]] > RANK[best[key][1]]:
            best[key] = (r["BU course"], r[lv], str(r["Notes"]))
# courses not in the Course Match sheet: hand-assigned counterparts
EXTRA_MAP = {("NEU","CS 2700"):("CAS CS 112",6), ("NEU","CS 3100"):("CAS CS 211",5), ("NEU","CS 2800"):("CAS CS 131",4),
             ("NEU","DS 3000"):("CAS CS 240",3), ("NEU","BIOL 2299"):("CAS BI 107",3), ("NEU","BIOL 3611"):("CAS CH 373",7),
             ("NEU","PSYC 3464"):("CAS PS 275",7), ("NEU","CHEM 2313"):("CAS CH 204",8),
             ("NYU","PSYCH-UA 11"):("CAS PS 205",7), ("NYU","MATH-UA 235"):("CAS MA 213",6)}
# explicit overlaps for courses used in the demo transcripts (shared topics out of 8)
K_OVERRIDE = {("NYU","PSYCH-UA 10"):6, ("NYU","PSYCH-UA 25"):5, ("NEU","CS 2100"):5, ("NEU","CHEM 1161"):5,
              ("NEU","BIOL 2301"):6, ("NYU","ECON-UA 266"):5}
for sheet, sc in (("Northeastern Courses", "NEU"), ("NYU Courses", "NYU")):
    for _, r in x[sheet].iterrows():
        code = r["Course code"].strip()
        if (sc, code) in EXTRA_MAP:
            bu, k = EXTRA_MAP[(sc, code)]; lvl_txt = "Not in match sheet (team mapping)"
        else:
            bu, lv, _n = best[(sc, code)]
            k = {"Likely equivalent": rng.choice([7, 8]), "Partial - syllabus review": rng.choice([5, 6]),
                 "Must be taken at BU": 8, "No equivalent found": 3}[lv]
            lvl_txt = lv
        k = K_OVERRIDE.get((sc, code), k)
        num = int("".join(ch for ch in code.split()[-1] if ch.isdigit()))
        lvl = (100 if num < 2000 else 200 if num < 3000 else 300) if sc == "NEU" else (100 if num < 100 else 200 if num < 300 else 300)
        derive(sc, bu, k, code, r["Course title"], int(r["Credits"]),
               f"{'NU' if sc=='NEU' else 'NYU'} catalog course (code/title/credits from hackathon workbook); description, outcomes and topics SYNTHETIC",
               level=lvl, note=f"Workbook match level: {lvl_txt}")

# ------------------------------------------------------------------ synthetic extras under NU / NYU (to ~200 total)
SYN_SRC = "SYNTHETIC course (not in the NU/NYU catalog; invented for test volume)"
PRE = {"NEU": dict(CS="CS", EC="ECON", PS="PSYC", BI="BIOL", CH="CHEM", MA="MATH"),
       "NYU": dict(CS="CSCI-UA", EC="ECON-UA", PS="PSYCH-UA", BI="BIOL-UA", CH="CHEM-UA", MA="MATH-UA")}
used_codes = {r["ext_id"] for r in ext_rows}
cnt = {}
def syn_code(sc, dept, lvl):
    pre = PRE[sc][dept]
    while True:
        cnt[(sc, pre, lvl)] = cnt.get((sc, pre, lvl), 0) + 1
        i = cnt[(sc, pre, lvl)]
        n = ({1: 1700, 2: 2700, 3: 3700}[lvl] + i * 3) if sc == "NEU" else ({1: 60, 2: 160, 3: 360}[lvl] + i * 3)
        code = f"{pre} {n}"
        if f"{sc}|{code}" not in used_codes:
            used_codes.add(f"{sc}|{code}"); return code
def derive_syn(sc, bu_code, k):
    bu = BU_BY[bu_code]
    title = bu["title"] if k >= 5 else (tcase(sorted(POOL[bu["program"]] - set(bu["topics"]))[rng.randrange(20)]) + " and " + tcase(bu["topics"][rng.randrange(8)]))
    cr = (5 if bu["dept"] in ("BI", "CH") else 4) if sc == "NEU" else 4
    return derive(sc, bu_code, k, syn_code(sc, bu["dept"], bu["level"] // 100), title[:60], cr, SYN_SRC)

FORCED_SYN = {("NYU","CAS EC 220"):8, ("NYU","CAS EC 250"):7, ("NYU","CAS EC 240"):6, ("NEU","CAS BI 210"):7}
syn_ref = {}
for (sc, b), k in FORCED_SYN.items():
    syn_ref[(sc, b)] = derive_syn(sc, b, k)
for sc in ("NEU", "NYU"):
    have = {r["gt_counterpart"] for r in ext_rows if r["school_code"] == sc}
    cands = [r["bu_code"] for r in bu_rows if r["bu_code"] not in have and not r["requirement_type"].startswith("Group C")]
    rng.shuffle(cands)
    for b in cands[:45]:
        derive_syn(sc, b, rng.choices([8, 7, 6, 5, 4, 3, 2], weights=[20, 22, 15, 15, 10, 10, 8])[0])

MISC = [
 ("NEU","ENGW 1111","First-Year Writing",4,"Academic","General education","TFRGEN 1TR","thesis development; academic argument; research and citation; revision; audience and purpose; source evaluation"),
 ("NEU","HIST 1130","Introduction to World History",4,"Academic","General education","TFRGEN 1TR","ancient civilizations; classical empires; world religions; trade networks; colonialism; historical sources"),
 ("NEU","SOCL 1101","Introduction to Sociology",4,"Academic","General education","TFRGEN 1TR","sociological imagination; culture; socialization; stratification; institutions; research methods"),
 ("NEU","FILM 1101","Film Analysis",4,"Academic","General education","TFRGEN 1TR","film form; cinematography; editing; genre; film history; critical writing"),
 ("NEU","MATH 0990","Algebra Foundations (developmental)",4,"Remedial","Mathematics",None,"linear equations; inequalities; polynomials; factoring; rational expressions; graphing"),
 ("NEU","PE 1100","Fitness Fundamentals",2,"Physical education","General education",None,"cardiovascular fitness; strength training; flexibility; nutrition basics; goal setting; wellness"),
 ("NEU","FYS 1000","First-Year Seminar",1,"Academic","General education","TFRGEN 1TR","college transition; academic integrity; study strategies; campus resources; reflection; goal setting"),
 ("NEU","MILS 1101","Military Science I (ROTC)",2,"ROTC","Military science",None,"military organization; leadership basics; land navigation; physical training; military history; values and ethics"),
 ("NEU","COOP 3945","Co-op Work Experience",4,"Internship","Career",None,"workplace learning; professional skills; reflective journal; supervisor evaluation; career planning; final report"),
 ("NEU","BIOL 4990","Directed Research in Biology",4,"Research","Biology",None,"research design; literature review; laboratory work; data analysis; scientific writing; poster presentation"),
 ("NEU","CS 1990","Introduction to Programming in Python",4,"Academic","Computer Science","CAS CS 1TR","variables and expressions; conditionals and loops; functions and parameters; lists and strings; file input and output; debugging and testing"),
 ("NYU","WRIT-UA 5","Writing Workshop",4,"Academic","General education","TFRGEN 1TR","academic argument; research and citation; source evaluation; revision; genre analysis; peer review"),
 ("NYU","HIST-UA 10","Modern World History",4,"Academic","General education","TFRGEN 1TR","industrialization; world wars; decolonization; Cold War; globalization; historical sources"),
 ("NYU","PHIL-UA 3","Introduction to Ethics",4,"Academic","General education","TFRGEN 1TR","ethical theories; utilitarianism; deontology; virtue ethics; applied ethics; moral argument"),
 ("NYU","SPAN-UA 1","Elementary Spanish I",4,"Academic","General education","TFRGEN 1TR","pronunciation; present tense; everyday vocabulary; conversation; Hispanic cultures; reading short texts"),
 ("NYU","ART-UA 5","Art Appreciation",4,"Academic","General education","TFRGEN 1TR","visual elements; art media; art history overview; museum analysis; design principles; art criticism"),
 ("NYU","COMM-UA 10","Public Speaking",4,"Academic","General education","TFRGEN 1TR","speech organization; audience analysis; delivery; persuasive speaking; visual aids; speech anxiety"),
 ("NYU","ECON-UA 980","Economics Internship",4,"Internship","Economics",None,"workplace learning; professional skills; reflective journal; supervisor evaluation; career planning; final report"),
 ("NYU","PHED-UA 10","Fitness and Wellness",2,"Physical education","General education",None,"cardiovascular fitness; strength training; flexibility; nutrition basics; goal setting; wellness"),
 ("NYU","MATH-UA 9","Algebra and Calculus Foundations (developmental)",4,"Remedial","Mathematics",None,"linear equations; functions; polynomials; exponential functions; logarithms; graphing"),
 ("NYU","PSYCH-UA 997","Independent Research in Psychology",4,"Research","Psychology",None,"research design; literature review; data collection; data analysis; scientific writing; presentation"),
 ("PSC","PSY 215","Psychology of Music",4,"Academic","Psychology","CAS PS 2TR","music perception; emotion and music; music and memory; musical development; music therapy; cultural differences in music"),
 ("SOI","ECO 210","Personal Finance",3,"Academic","Economics","CAS EC 1TR","budgeting; credit; saving and investing; insurance; taxes; retirement planning"),
 ("SOI","BUS 101","Introduction to Business",3,"Academic","General education","TFRGEN 1TR","business functions; management; marketing; accounting basics; entrepreneurship; business ethics"),
]
for s, code, title, cr, ctype, area, elec, topics in MISC:
    t = [v.strip() for v in topics.split(";")]
    cal = SCH[s]["calendar"]
    gt = "CAS CS 111" if code == "CS 1990" else ""
    src = SYN_SRC if s in ("NEU", "NYU") else "Fictional helper school (synthetic)"
    add_row(dict(school_code=s, course_code=code, title=title, credits=cr, calendar=cal, units_if_transferred=units(cr, cal),
                 program_area=area, course_type=ctype, level=100, source=src,
                 description=f"{title}. Topics include {', '.join(t[:-1])} and {t[-1]}.", learning_outcomes=outcomes(t), topics=t,
                 gt_counterpart=gt, gt_overlap=(0.75 if gt else 0.0), gt_tier=("Duplicate of CS 111 content" if gt else "No BU equivalent"),
                 notes="", elective_code=elec))

def ext(sc, code): return BY_CODE[f"{sc}|{code}"]

# ------------------------------------------------------------------ decision logic
def elective_code_for(r):
    if r.get("elective_code"): return r["elective_code"]
    if not r["gt_counterpart"]: return "TFRGEN 1TR"
    return f"CAS {r['gt_counterpart'].split()[1]} {1 if r['level'] < 200 else 2}TR"
INELIGIBLE = {"Remedial": "NC-REMEDIAL", "Physical education": "NC-PE", "Vocational": "NC-VOC", "ROTC": "NC-ROTC",
              "Internship": "NC-INTERNSHIP", "Research": "NC-RESEARCH"}
def course_decision(r):
    if SCH[r["school_code"]]["accreditation"].startswith("Not"): return "No credit", "TFRGEN NOCRDT", "NC-ACCRED"
    if r["course_type"] in INELIGIBLE: return "No credit", "TFRGEN NOCRDT", INELIGIBLE[r["course_type"]]
    if r["credits"] == 1: return "No credit", "TFRGEN NOCRDT", "NC-ONECREDIT"
    bu = r["gt_counterpart"]
    if r["course_code"] == "CS 1990": return "Equivalent", "CAS CS 111", "EQ-EVALUATOR"
    if not bu: return "Elective", elective_code_for(r), "EL-NOEQUIV"
    ov = r["gt_overlap"]
    if ov >= 0.8:
        if BU_BY[bu]["requirement_type"].startswith("Group C"): return "Elective", elective_code_for(r), "EL-RESIDENCY"
        return "Equivalent", bu, "EQ-CONTENT"
    if ov >= 0.5:
        if ov >= 0.75 and rng.random() < 0.7: return "Equivalent", bu, "EQ-EVALUATOR"
        return "Elective", elective_code_for(r), "EL-PARTIAL"
    return "Elective", elective_code_for(r), "EL-LOWOVERLAP"

# ------------------------------------------------------------------ students and transcript lines (school, term, code, grade)
STUDENTS = [
 dict(student_id="SYN-24001", name="Maya R. Delgado", intended_major="Psychology", bu_school="College of Arts & Sciences", bu_start_term="Fall 2026",
      story="Demo student from NYU: 6 courses (3 existing matches, 2 maybe, 1 summer quarter-system course)"),
 dict(student_id="SYN-24002", name="Jordan A. Reyes", intended_major="Computer Science", bu_school="College of Arts & Sciences", bu_start_term="Fall 2026",
      story="From Northeastern. Rules showcase: C-, developmental math, P/F, 1-credit seminar, duplicate, CS Group C residency, 7-year-old course, incomplete syllabus"),
 dict(student_id="SYN-24003", name="Aisha K. Bello", intended_major="Biology", bu_school="College of Arts & Sciences", bu_start_term="Fall 2026",
      story="From Northeastern. 5-credit lab courses; NU's one-semester general chemistry (maybe); research course; same-year conflicting decisions"),
 dict(student_id="SYN-24004", name="Liam O. Novak", intended_major="Economics", bu_school="College of Arts & Sciences", bu_start_term="Fall 2026",
      story="Northeastern then NYU (+ one non-accredited online school). 68-unit cap, ROTC, internship, superseded decision, prompt-injection syllabus, reuses Maya's approved course"),
]
EC220, EC250, EC240, BI210 = (syn_ref[k]["course_code"] for k in (("NYU","CAS EC 220"),("NYU","CAS EC 250"),("NYU","CAS EC 240"),("NEU","CAS BI 210")))
LINES = [
 ("SYN-24001","NYU","Fall 2024","PSYCH-UA 1","A-"),("SYN-24001","NYU","Fall 2024","MATH-UA 121","B+"),("SYN-24001","NYU","Fall 2024","ECON-UA 2","B"),
 ("SYN-24001","NYU","Spring 2025","PSYCH-UA 10","A"),("SYN-24001","NYU","Spring 2025","PSYCH-UA 25","B+"),("SYN-24001","PSC","Summer 2025","PSY 215","B"),

 ("SYN-24002","NEU","Fall 2019","HIST 1130","B"),
 ("SYN-24002","NEU","Fall 2023","CS 2000","A"),("SYN-24002","NEU","Fall 2023","MATH 1341","C-"),("SYN-24002","NEU","Fall 2023","MATH 0990","A"),
 ("SYN-24002","NEU","Fall 2023","PE 1100","P"),("SYN-24002","NEU","Fall 2023","FYS 1000","A"),
 ("SYN-24002","NEU","Spring 2024","CS 2100","B+"),("SYN-24002","NEU","Spring 2024","CS 1800","B"),("SYN-24002","NEU","Spring 2024","CS 1990","A-"),
 ("SYN-24002","NEU","Spring 2024","FILM 1101","P"),
 ("SYN-24002","NEU","Fall 2024","CS 2700","B"),("SYN-24002","NEU","Fall 2024","CS 3650","B"),("SYN-24002","NEU","Fall 2024","CS 4400","A-"),
 ("SYN-24002","NEU","Fall 2024","MATH 2331","B+"),

 ("SYN-24003","NEU","Fall 2024","BIOL 1107","A"),("SYN-24003","NEU","Fall 2024","CHEM 1161","B+"),("SYN-24003","NEU","Fall 2024","ENGW 1111","A-"),
 ("SYN-24003","NEU","Spring 2025","BIOL 1113","B+"),("SYN-24003","NEU","Spring 2025","MATH 1341","A"),("SYN-24003","NEU","Spring 2025","BIOL 2299","B"),
 ("SYN-24003","NEU","Fall 2025","BIOL 2301","B+"),("SYN-24003","NEU","Fall 2025","CHEM 2311","C+"),("SYN-24003","NEU","Fall 2025",BI210,"A-"),
 ("SYN-24003","NEU","Spring 2026","BIOL 3611","B+"),("SYN-24003","NEU","Spring 2026","CHEM 2313","B"),("SYN-24003","NEU","Spring 2026","BIOL 4990","A"),

 ("SYN-24004","NEU","Fall 2022","ECON 1116","A"),("SYN-24004","NEU","Fall 2022","MATH 1341","B"),("SYN-24004","NEU","Fall 2022","ENGW 1111","A-"),
 ("SYN-24004","NEU","Fall 2022","MILS 1101","A"),("SYN-24004","NEU","Spring 2023","ECON 1115","B+"),("SYN-24004","NEU","Spring 2023","MATH 1342","B-"),
 ("SYN-24004","NEU","Spring 2023","HIST 1130","B"),("SYN-24004","NEU","Spring 2023","SOCL 1101","A"),
 ("SYN-24004","SOI","Summer 2023","ECO 210","A"),("SYN-24004","SOI","Summer 2023","BUS 101","A"),
 ("SYN-24004","NYU","Fall 2023","PSYCH-UA 10","B+"),("SYN-24004","NYU","Fall 2023","COMM-UA 10","A-"),("SYN-24004","NYU","Fall 2023","ART-UA 5","B+"),
 ("SYN-24004","NYU","Spring 2024","SPAN-UA 1","B"),("SYN-24004","NYU","Spring 2024","ECON-UA 10","B+"),("SYN-24004","NYU","Spring 2024","PHIL-UA 3","A"),
 ("SYN-24004","NYU","Fall 2024","ECON-UA 12","B"),("SYN-24004","NYU","Fall 2024","ECON-UA 18","A-"),("SYN-24004","NYU","Fall 2024","MATH-UA 140","B"),
 ("SYN-24004","NYU","Spring 2025","ECON-UA 266","B"),("SYN-24004","NYU","Spring 2025",EC220,"A-"),
 ("SYN-24004","NYU","Fall 2025",EC250,"B+"),("SYN-24004","NYU","Fall 2025",EC240,"B"),("SYN-24004","NYU","Spring 2026","ECON-UA 980","P"),
]

# decisions: everything on transcripts is decided (train) except the open "maybe" courses
OPEN = {("NYU","PSYCH-UA 10"),("NYU","PSYCH-UA 25"),("NEU","CS 2100"),("NEU","CS 2700"),("NEU","CHEM 1161"),("NEU","BIOL 2301"),
        ("NEU","BIOL 3611"),("NEU","BIOL 2299"),("NEU","CHEM 2311"),("NYU","ECON-UA 266"),("NYU",EC240)}
open_ids = {f"{s}|{c}" for s, c in OPEN}
EVALS = {"Computer Science": ["Evaluator CS-A","Evaluator CS-B"], "Economics": ["Evaluator EC-A","Evaluator EC-B"],
         "Psychology": ["Evaluator PS-A","Evaluator PS-B"], "Biology": ["Evaluator BI-A","Evaluator BI-B"], "Mathematics": ["Evaluator MA-A","Evaluator MA-B"]}
decisions = []
def add_decision(r, split, cy=None, override=None, date=None, note=""):
    d, code, reason = override or course_decision(r)
    decisions.append(dict(decision_id=f"D-{len(decisions)+1:04d}", ext_id=r["ext_id"], school_code=r["school_code"], source_course=r["course_code"],
        source_title=r["title"], source_credits=r["credits"], calendar=r["calendar"], decision=d, bu_course=code,
        units_awarded=(0.0 if d == "No credit" else r["units_if_transferred"]), bu_grade=("TX" if d == "No credit" else "T"), reason_code=reason,
        overlap_pct=int(round(r["gt_overlap"]*100)) if r["gt_counterpart"] else None,
        decided_by=rng.choice(EVALS.get(r["program_area"], ["Credit Evaluation Office"])) if r["course_type"] == "Academic" else "Credit Evaluation Office",
        department=r["program_area"], decision_date=date or f"{rng.choice([2024,2025])}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        catalog_year=cy or rng.choice(["2023-24","2024-25"]), reusable="Yes" if split == "train" else "No", split=split, notes=note))

used = set()
for sid, sc, term, code, g in LINES:
    r = ext(sc, code)
    if r["ext_id"] in open_ids or r["ext_id"] in used: continue
    if (sc, code) == ("NYU", "ECON-UA 18"):
        add_decision(r, "train", "2022-23", ("Elective", "CAS EC 2TR", "EL-PARTIAL"), "2023-03-14", "Older decision; superseded")
        add_decision(r, "train", "2024-25", ("Equivalent", "CAS EC 203", "EQ-EVALUATOR"), "2025-02-10", "Newer decision for later catalog year")
    elif (sc, code) == ("NEU", BI210):
        add_decision(r, "train", "2024-25", None, "2024-11-05")
        add_decision(r, "train", "2024-25", ("Elective", "CAS BI 2TR", "EL-PARTIAL"), "2025-06-02", "Conflicts with an earlier decision in the same catalog year")
    else:
        add_decision(r, "train")
    used.add(r["ext_id"])
for misc in ("WRIT-UA 5","HIST-UA 10","PHED-UA 10","MATH-UA 9","PSYCH-UA 997"):
    r = ext("NYU", misc); add_decision(r, "train"); used.add(r["ext_id"])
for misc in ("COOP 3945",):
    r = ext("NEU", misc); add_decision(r, "train"); used.add(r["ext_id"])
pool = [r for r in ext_rows if r["ext_id"] not in used and r["ext_id"] not in open_ids and r["course_type"] == "Academic"
        and r["gt_counterpart"] and r["school_code"] in ("NEU","NYU")]
rng.shuffle(pool)
n_train = 100 - 30 - len(decisions)
for r in pool[:n_train]: add_decision(r, "train"); used.add(r["ext_id"])
hold = sorted(pool[n_train:], key=lambda r: (r["gt_overlap"], r["ext_id"]))
holdout = hold[::max(1, len(hold)//30)][:30]
for r in holdout: add_decision(r, "holdout")

# syllabi
SYLLABI = {}
def reg(sc, code, state, who, note): SYLLABI[f"{sc}|{code}"] = dict(state=state, used_by=who, note=note)
reg("NYU","PSYCH-UA 10","complete","Maya Delgado","Maybe 1: on file at upload (~75% overlap with CAS PS 211; workbook: partial, statistics vs experimental design)")
reg("NYU","PSYCH-UA 25","complete-late","Maya Delgado","Maybe 2: missing at upload (TS); upload in demo step 7 (~62% overlap with CAS PS 231)")
reg("NEU","CS 2100","complete","Jordan Reyes","Partial (~62%) with CAS CS 112; workbook notes NU splits CS 112 across CS 2100 + CS 2700")
reg("NEU","CS 2700","incomplete","Jordan Reyes","INCOMPLETE: no learning outcomes or weekly schedule -> TM request")
reg("NEU","CHEM 1161","complete","Aisha Bello","NU one-semester general chemistry (~62% with CAS CH 101; may map to CH 101 or CH 102)")
reg("NEU","BIOL 2301","complete","Aisha Bello","Partial (~75%) with CAS BI 206 (genetics + molecular biology)")
reg("NEU","BIOL 3611","complete","Aisha Bello","High overlap (~88%) with CAS CH 373 Biochemistry 1 -> propose equivalent")
reg("NEU","BIOL 2299","complete","Aisha Bello","Low overlap (~38%) with CAS BI 107 -> elective expected")
reg("NYU","ECON-UA 266","complete-injection","Liam Novak","RED-TEAM: contains a prompt-injection line; AI must ignore it (~62% with CAS EC 204)")
for r in holdout[-3:]:
    SYLLABI[r["ext_id"]] = dict(state="complete", used_by="Evaluation set", note=f"Held-out course (~{int(r['gt_overlap']*100)}% overlap with {r['gt_counterpart']})")

GRADE_OK = {"A","A-","B+","B","B-","C+","C"}
def lookup(eid):
    ds = sorted([d for d in decisions if d["ext_id"] == eid and d["split"] == "train"], key=lambda d: (d["catalog_year"], d["decision_date"]))
    if not ds: return None, ""
    n = ds[-1]
    if any(d["catalog_year"] == n["catalog_year"] and d["decision"] != n["decision"] for d in ds):
        return n, "CONFLICT: same catalog year, different decisions -> flag for department"
    if len({d["decision"] for d in ds}) > 1: return n, "Older conflicting decision superseded by newest catalog year"
    return n, ""

lines = [dict(student_id=sid, school_code=sc, term=term, ext_id=ext(sc, code)["ext_id"], course_code=code, title=ext(sc, code)["title"],
              credits=ext(sc, code)["credits"], calendar=ext(sc, code)["calendar"], grade=g) for sid, sc, term, code, g in LINES]
def evaluate(sid, start=2026, cap=68.0):
    out, used_bu = [], set()
    for ln in [l for l in lines if l["student_id"] == sid]:
        r = BY_CODE[ln["ext_id"]]; u = units(ln["credits"], ln["calendar"])
        res = dict(status="", bu_course="", units=0.0, bu_grade="", reason_code="", flag="")
        NC = lambda rc: res.update(status="Posted - no credit", bu_course="TFRGEN NOCRDT", bu_grade="TX", reason_code=rc)
        if SCH[ln["school_code"]]["accreditation"].startswith("Not"): NC("NC-ACCRED")
        elif r["course_type"] in INELIGIBLE: NC(INELIGIBLE[r["course_type"]])
        elif ln["credits"] == 1: NC("NC-ONECREDIT")
        elif ln["grade"] in ("P","NP","S","U"): NC("NC-PASSFAIL")
        elif ln["grade"] not in GRADE_OK: NC("NC-GRADE")
        elif int(ln["term"].split()[1]) <= start - 5: res.update(status="Pending - age review (5+ years old)", reason_code="RV-AGE")
        else:
            dec, flag = lookup(r["ext_id"])
            if dec:
                code, reason = dec["bu_course"], dec["reason_code"]
                if dec["decision"] == "Equivalent" and code in used_bu:
                    code, reason = f"CAS {code.split()[1]} {1 if r['level'] < 200 else 2}TR", "EL-DUPLICATE"
                res.update(status="Matched - existing equivalency", bu_course=code, units=u, bu_grade="T", reason_code=reason, flag=flag)
                if dec["decision"] == "Equivalent" and reason != "EL-DUPLICATE": used_bu.add(dec["bu_course"])
            else:
                st = SYLLABI.get(r["ext_id"], {}).get("state")
                if st in ("complete","complete-injection"): res.update(status=f"Maybe - syllabus on file; AI tier: {tier(r['gt_overlap'])}", reason_code="PD-REVIEW")
                elif st == "incomplete": res.update(status="Maybe - syllabus incomplete (TM request)", reason_code="PD-TM")
                else: res.update(status="Maybe - syllabus requested (TS)", reason_code="PD-TS")
                if sid == "SYN-24004" and ln["course_code"] == "PSYCH-UA 10":
                    res["flag"] = "Same course as Maya's PSYCH-UA 10: matches instantly once her decision is approved (test T15)"
        out.append({**ln, **res, "units_if_approved": u, "gt_counterpart": r["gt_counterpart"],
                    "gt_overlap_pct": int(r["gt_overlap"]*100) if r["gt_counterpart"] else None})
    run = 0.0
    for o in out:
        c = o["units"] if o["units"] else (o["units_if_approved"] if o["status"].startswith(("Maybe","Pending")) else 0.0)
        if c and run + c > cap:
            allowed = max(0.0, round(cap - run, 2))
            o["flag"] = (o["flag"] + "; " if o["flag"] else "") + f"68-unit cap reached: only {allowed} of {c} units can count"
            if o["units"]: o["units"] = allowed
            run = cap
        else: run += c
    for o in out:
        if o["bu_course"].startswith("CAS BI ") and o["bu_course"] not in ("CAS BI 107","CAS BI 108") and not o["bu_course"].endswith("TR"):
            o["flag"] = (o["flag"] + "; " if o["flag"] else "") + "Biology residency: still needs 5 BI courses beyond BI 107/108 at BU (credit unaffected)"
        if sid == "SYN-24004" and (o["gt_counterpart"] or "").startswith("CAS EC 2"):
            o["flag"] = (o["flag"] + "; " if o["flag"] else "") + "Econ 200+ cap applies only after matriculation: not applied"
    return out
expected = [o for s in STUDENTS for o in evaluate(s["student_id"])]

json.dump(dict(bu=bu_rows, schools=SCHOOLS, ext=ext_rows, decisions=decisions, students=STUDENTS, lines=expected, syllabi=SYLLABI),
          open(os.path.join(HERE, "data.json"), "w"), indent=1)
import collections
print("BU", len(bu_rows), "EXT", len(ext_rows), collections.Counter(r["school_code"] for r in ext_rows),
      "real", sum(1 for r in ext_rows if "catalog course" in r["source"]), "DEC", len(decisions),
      collections.Counter(d["split"] for d in decisions), "lines", len(expected), "syllabi", len(SYLLABI))
