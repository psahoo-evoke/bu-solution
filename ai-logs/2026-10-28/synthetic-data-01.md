# synthetic-data-01 · First synthetic data set (fictional colleges)

| Field | Value |
| --- | --- |
| Date | 2026-10-28 |
| Agent (role) | synthetic-data |
| Tool / model | Solutionauts AI (Cowork) |
| Human owner | Data / QA lead |
| Trigger | "can you provide transcript certificates and syllabus also synthetic data" (full brief scale; PDFs + Excel + CSV/JSON) |

## Output
- 150 BU courses, ~190 external courses from 4 fictional colleges, ~100 past decisions, 4 students, 7 transcripts, 12 syllabi
- Controlled topic overlap per external course, so the true match tier is known (gt_* columns)

## Human review
- **Rejected the source schools**: the hackathon supplied Northeastern and NYU data only -> superseded by synthetic-data-02

## Verification
- Sponsor worked examples reproduced (B elective 3 units; 4 qtr credits -> 2.67; C- -> TX; remedial -> TX)
- Workbook recalculated with 0 formula errors

## Commit
superseded (not imported)
