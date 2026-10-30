/** The parts of a syllabus an evaluator compares against a BU course: what it covers, what students can do after
 *  it, and the week-by-week plan. Everything else (header, assessment weights, policies) is left out of the view. */
export interface SyllabusWeek {
  week: string;
  topic: string;
  activity: string;
}

export interface SyllabusSections {
  /** null: the heading is not in the text. A string with no list/rows: the syllabus gives only a placeholder note. */
  description: string | null;
  outcomes: string[];
  outcomesNote: string | null;
  weeks: SyllabusWeek[];
  weeksNote: string | null;
  /** False when none of the three headings were found (e.g. an uploaded syllabus with its own layout). */
  recognised: boolean;
}

type Key = 'description' | 'outcomes' | 'schedule' | 'other';

const HEADINGS: [RegExp, Key][] = [
  [/^course description$/i, 'description'],
  [/^(learning outcomes|learning objectives|course objectives)$/i, 'outcomes'],
  [/^(weekly schedule|course schedule|schedule|course outline)$/i, 'schedule'],
  [/^(assessment|grading|materials and policies|materials|policies|required materials)$/i, 'other'],
];
/** pdfplumber keeps the page footer, which can land in the middle of a section. */
const FOOTER = /syllabus\s*-\s*page\s+\d+\s*$/i;
const SCHEDULE_HEADER = /^week\s+topic\b/i;
const OUTCOMES_INTRO = /^by the end of (the|this) course/i;
const NUMBERED = /^(\d{1,2})[.)]\s+(.*)$/;
const WEEK_ROW = /^(\d{1,2})\s+(.+)$/;
/** Assessment names seen at the end of a schedule row; anything else stays in the topic column. */
const ACTIVITY = new RegExp(
  '\\s(problem sets?|in-class exercises?|quiz(zes)?|case stud(y|ies)|reading and discussion|readings?|discussion|' +
    'midterm( exam)?|final exam( \\/ project)?|final project|exam|labs?( report)?|project|presentation|essay|' +
    'homework|assignment|paper|none)$',
  'i',
);

export function parseSyllabus(text: string | null | undefined): SyllabusSections {
  const sections: Partial<Record<Key, string[]>> = {};
  let current: Key | null = null;
  for (const raw of (text ?? '').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || FOOTER.test(line)) continue;
    const heading = HEADINGS.find(([re]) => re.test(line));
    if (heading) {
      current = heading[1];
      sections[current] ??= [];
      continue;
    }
    if (current) sections[current]!.push(line);
  }

  const description = sections.description ? sections.description.join(' ') || null : null;

  const outcomes: string[] = [];
  const outcomeLoose: string[] = [];
  for (const line of sections.outcomes ?? []) {
    if (OUTCOMES_INTRO.test(line)) continue;
    const m = NUMBERED.exec(line) ?? /^[•\-–*]\s+(.*)$/.exec(line);
    if (m) outcomes.push(m[m.length - 1]);
    else if (outcomes.length) outcomes[outcomes.length - 1] += ' ' + line;   // wrapped item
    else outcomeLoose.push(line);
  }

  const rows: string[][] = [];
  const weekLoose: string[] = [];
  for (const line of sections.schedule ?? []) {
    if (SCHEDULE_HEADER.test(line)) continue;
    const m = WEEK_ROW.exec(line);
    if (m) rows.push([m[1], m[2]]);
    else if (rows.length) rows[rows.length - 1][1] += ' ' + line;            // wrapped row
    else weekLoose.push(line);
  }
  const weeks = rows.map(([week, rest]) => {
    const a = ACTIVITY.exec(rest);
    return a && a.index > 0
      ? { week, topic: rest.slice(0, a.index).trim(), activity: rest.slice(a.index).trim() }
      : { week, topic: rest, activity: '' };
  });

  return {
    description,
    outcomes,
    outcomesNote: outcomes.length ? null : outcomeLoose.join(' ') || null,
    weeks,
    weeksNote: weeks.length ? null : weekLoose.join(' ') || null,
    recognised: !!(sections.description || sections.outcomes || sections.schedule),
  };
}
