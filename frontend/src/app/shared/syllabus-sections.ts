/** The parts of a syllabus an evaluator compares against a BU course: what it covers and what students can do after
 *  it. Everything else (header, schedule, assessment weights, policies) is left out of the view. */
export interface SyllabusSections {
  /** null: the heading is not in the text. */
  description: string | null;
  outcomes: string[];
  /** The placeholder an incomplete syllabus gives instead of a list ("To be discussed in the first class"). */
  outcomesNote: string | null;
  /** False when neither heading was found (e.g. an uploaded syllabus with its own layout). */
  recognised: boolean;
}

type Key = 'description' | 'outcomes' | 'other';

const HEADINGS: [RegExp, Key][] = [
  [/^course description$/i, 'description'],
  [/^(learning outcomes|learning objectives|course objectives)$/i, 'outcomes'],
  // Headings that end the two sections above; their content is not shown.
  [/^(weekly schedule|course schedule|schedule|course outline)$/i, 'other'],
  [/^(assessment|grading|materials and policies|materials|policies|required materials)$/i, 'other'],
];
/** pdfplumber keeps the page footer, which can land in the middle of a section. */
const FOOTER = /syllabus\s*-\s*page\s+\d+\s*$/i;
const OUTCOMES_INTRO = /^by the end of (the|this) course/i;
const NUMBERED = /^(\d{1,2})[.)]\s+(.*)$/;

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

  return {
    description,
    outcomes,
    outcomesNote: outcomes.length ? null : outcomeLoose.join(' ') || null,
    recognised: !!(sections.description || sections.outcomes),
  };
}
