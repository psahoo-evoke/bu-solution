"""Extract the Notes column of the hackathon workbook's "Course Match" sheet into seed/workbook_notes.csv.

One row per (peer course, BU course) pair that has a note: school_code, course_code, bu_course, match_level, note.
The app shows these to staff as reference only (never in the AI prompt, never to students). Standard library only
(zipfile + xml), so it runs without pandas/openpyxl:  python scripts/synthetic/extract_workbook_notes.py"""
import csv
import os
import re
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
WB = os.path.join(HERE, "..", "..", "data", "BU_Transfer_Program_Course_Match.xlsx")
OUT = os.path.join(HERE, "..", "..", "data", "synthetic", "seed", "workbook_notes.csv")
SHEET = "Course Match"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
PEERS = (("NEU", "Northeastern course", "NU match level"), ("NYU", "NYU course", "NYU match level"))
EMPTY = {"", "-", "—", "–", "nan", "none", "n/a"}


def _sheet_rows(z: zipfile.ZipFile, name: str) -> list[list[str]]:
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = next(s.get(f"{{{NS['r']}}}id") for s in wb.find("m:sheets", NS) if s.get("name") == name)
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels.findall("rel:Relationship", NS) if r.get("Id") == rid)
    path = "xl/" + target.lstrip("/").removeprefix("xl/")
    rows = []
    for row in ET.fromstring(z.read(path)).find("m:sheetData", NS):
        cells = {}
        for c in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            idx = 0
            for ch in col:
                idx = idx * 26 + ord(ch) - 64
            if c.get("t") == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
            else:
                v = c.find("m:v", NS)                       # formulas keep their cached value here
                val = "" if v is None else (shared[int(v.text)] if c.get("t") == "s" else v.text or "")
            cells[idx - 1] = val.strip()
        rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
    return rows


def main() -> None:
    with zipfile.ZipFile(WB) as z:
        rows = _sheet_rows(z, SHEET)
    head_i = next(i for i, r in enumerate(rows) if "Notes" in r and "BU course" in r)
    head = rows[head_i]
    col = {h: head.index(h) for h in head if h}
    out, seen = [], set()
    for r in rows[head_i + 1:]:
        get = lambda h: r[col[h]] if col[h] < len(r) else ""   # noqa: E731
        note, bu = get("Notes"), get("BU course")
        if note.lower() in EMPTY or not bu:
            continue
        for school, course_col, level_col in PEERS:
            code = get(course_col)
            if code.lower() in EMPTY:
                continue
            key = (school, code, bu)
            if key not in seen:
                seen.add(key)
                out.append(dict(school_code=school, course_code=code, bu_course=bu, match_level=get(level_col), note=note))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["school_code", "course_code", "bu_course", "match_level", "note"])
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} notes -> {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
