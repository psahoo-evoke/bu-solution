import { parseSyllabus } from './syllabus-sections';

const FULL = `SYNTHETIC TEST SYLLABUS - source institution (test data): Northeastern University
CS 2100: Program Design and Implementation 1
Credits 5 semester credits Term Fall 2024
Course description
Program Design and Implementation 1. Topics include discrete probability, algorithm efficiency, language
paradigms and stacks and queues.
Learning outcomes
By the end of the course, students will be able to:
1. Explain the core ideas of discrete probability.
2. Apply algorithm efficiency to solve
standard problems.
Weekly schedule
Week Topic Activity / assessment
1 Discrete probability Problem set
2 Discrete probability (continued) In-class exercise
EvoHack 2026 test data. Fictional student; invented grades and content. Not issued by any institution. Syllabus - page 1
7 Review and midterm Midterm exam
12 Sorting algorithms (continued) Reading and discussion
14 Review and synthesis Final exam / project
15 Guest lecture
Assessment
Component Weight
Quizzes 15%
Materials and policies
Policies: see the institution's own catalog.`;

describe('parseSyllabus', () => {
  it('keeps only the description, the outcomes and the weekly schedule', () => {
    const v = parseSyllabus(FULL);
    expect(v.recognised).toBe(true);
    expect(v.description).toBe(
      'Program Design and Implementation 1. Topics include discrete probability, algorithm efficiency, language paradigms and stacks and queues.',
    );
    expect(v.outcomes).toEqual([
      'Explain the core ideas of discrete probability.',
      'Apply algorithm efficiency to solve standard problems.',
    ]);
    expect(v.weeks).toEqual([
      { week: '1', topic: 'Discrete probability', activity: 'Problem set' },
      { week: '2', topic: 'Discrete probability (continued)', activity: 'In-class exercise' },
      { week: '7', topic: 'Review and midterm', activity: 'Midterm exam' },
      { week: '12', topic: 'Sorting algorithms (continued)', activity: 'Reading and discussion' },
      { week: '14', topic: 'Review and synthesis', activity: 'Final exam / project' },
      { week: '15', topic: 'Guest lecture', activity: '' },
    ]);
    expect(JSON.stringify(v)).not.toContain('Quizzes 15%');
  });

  it('shows the placeholder an incomplete syllabus gives instead of a list', () => {
    const v = parseSyllabus(`Course description
Data Structures.
Learning outcomes
To be discussed in the first class meeting.
Course schedule
A detailed course outline will be distributed in class.
Assessment`);
    expect(v.outcomes).toEqual([]);
    expect(v.outcomesNote).toBe('To be discussed in the first class meeting.');
    expect(v.weeks).toEqual([]);
    expect(v.weeksNote).toBe('A detailed course outline will be distributed in class.');
  });

  it('reports an empty schedule and missing sections', () => {
    const v = parseSyllabus('Course description\nBiochemistry.\nWeekly schedule\nWeek Topic Activity / assessment\nAssessment');
    expect(v.weeks).toEqual([]);
    expect(v.weeksNote).toBeNull();
    expect(v.outcomes).toEqual([]);
    expect(v.outcomesNote).toBeNull();
  });

  it('does not recognise a syllabus with its own layout, so the raw text is shown', () => {
    expect(parseSyllabus('Intro to Psych\nTopics: memory, learning').recognised).toBe(false);
    expect(parseSyllabus(null).recognised).toBe(false);
  });
});
