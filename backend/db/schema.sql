-- TransferIQ PostgreSQL schema (docs/data-model.md). Not used by the hackathon slice, which runs in memory
-- (backend/app/store.py); this is the target for the Azure deployment (ADR 0002: own equivalency table).

CREATE TABLE bu_courses (
    bu_code            text PRIMARY KEY,                  -- e.g. 'CAS CS 111'
    dept               text NOT NULL,
    title              text NOT NULL,
    program            text NOT NULL,
    requirement_type   text NOT NULL,
    level              integer NOT NULL,
    credits            numeric(4,2) NOT NULL,
    residency_rule     text NOT NULL DEFAULT '',
    description        text NOT NULL,
    learning_outcomes  text[] NOT NULL DEFAULT '{}',
    topics             text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE schools (
    school_code    text PRIMARY KEY,
    name           text NOT NULL UNIQUE,
    calendar       text NOT NULL CHECK (calendar IN ('Semester', 'Quarter')),
    accreditation  text NOT NULL,
    role           text
);

CREATE TABLE external_courses (
    ext_id             text PRIMARY KEY,                  -- 'SCHOOL|CODE'
    school_code        text NOT NULL REFERENCES schools,
    course_code        text NOT NULL,
    title              text NOT NULL,
    credits            numeric(4,2) NOT NULL,
    calendar           text NOT NULL CHECK (calendar IN ('Semester', 'Quarter')),
    course_type        text NOT NULL DEFAULT 'Academic',
    program_area       text,
    level              integer,
    source             text,
    description        text,
    learning_outcomes  text[] NOT NULL DEFAULT '{}',
    topics             text[] NOT NULL DEFAULT '{}',
    elective_code      text,
    UNIQUE (school_code, course_code)
);

-- Ground truth lives in a separate table so the matcher's query path cannot select it (eval only).
CREATE TABLE external_courses_gt (
    ext_id          text PRIMARY KEY REFERENCES external_courses,
    gt_counterpart  text,
    gt_overlap      numeric(4,3),
    gt_tier         text
);

CREATE TABLE decisions (
    decision_id     text PRIMARY KEY,
    ext_id          text NOT NULL REFERENCES external_courses,
    decision        text NOT NULL CHECK (decision IN ('Equivalent', 'Elective', 'No credit')),
    bu_course       text NOT NULL,                       -- BU course, '... nTR' elective or 'TFRGEN NOCRDT'
    units_awarded   numeric(5,2),
    reason_code     text NOT NULL,
    reusable        boolean NOT NULL DEFAULT true,
    split           text NOT NULL DEFAULT 'runtime' CHECK (split IN ('train', 'holdout', 'runtime')),
    catalog_year    text NOT NULL,                       -- '2025-26'
    decided_by      text NOT NULL,
    decision_date   timestamptz NOT NULL DEFAULT now(),
    ai_suggestion   text,
    ai_agreed       boolean,
    note            text NOT NULL DEFAULT '',
    overlap_pct     integer                              -- evaluator-recorded overlap (seed decisions)
);
CREATE INDEX decisions_lookup ON decisions (ext_id, catalog_year, decision_date) WHERE split <> 'holdout';

-- Non-reusable decisions apply only to the students they were made for.
CREATE TABLE decision_scope (
    decision_id  text REFERENCES decisions ON DELETE CASCADE,
    student_id   text,
    PRIMARY KEY (decision_id, student_id)
);

-- The app reads equivalencies only through this view: holdout decisions are invisible (R10/R11).
CREATE VIEW equivalency_table AS
    SELECT * FROM decisions WHERE split <> 'holdout';

CREATE TABLE students (
    student_id      text PRIMARY KEY,
    name            text NOT NULL,
    intended_major  text,
    bu_school       text,
    bu_start_term   text NOT NULL,                      -- 'Fall 2026'
    email           text,                               -- columns below exist in bu-solution-pg; not used by the API
    phone           text,
    address         text,
    previous_school text
);

CREATE TABLE transcript_lines (
    student_id   text NOT NULL REFERENCES students,
    ext_id       text NOT NULL REFERENCES external_courses,
    term         text NOT NULL,
    seq          integer NOT NULL,                       -- transcript order (R17 cap is applied in this order)
    school_code  text NOT NULL REFERENCES schools,
    course_code  text NOT NULL,
    title        text,
    credits      numeric(4,2) NOT NULL,
    calendar     text NOT NULL,
    grade        text NOT NULL,
    PRIMARY KEY (student_id, ext_id, term)
);

CREATE TABLE syllabi (
    ext_id              text PRIMARY KEY REFERENCES external_courses,
    state               text NOT NULL CHECK (state IN ('complete', 'incomplete', 'missing', 'complete-injection')),
    blob_url            text,
    missing_sections    text[] NOT NULL DEFAULT '{}',
    injection_detected  boolean NOT NULL DEFAULT false,
    received_at         timestamptz,
    source_file         text,                           -- bundled seed PDF, relative to data/synthetic
    seed_state          text,                           -- state in syllabi_index.csv (e.g. complete-late)
    extracted_text      text NOT NULL DEFAULT ''        -- text the matcher reads (untrusted, ADR 0004)
);

-- Registrar posting step (app/main.py POST /postings): an approved line becomes posted (T).
CREATE TABLE postings (
    student_id   text NOT NULL,
    ext_id       text NOT NULL,
    term         text NOT NULL,
    decision_id  text,
    posted_at    timestamptz NOT NULL,
    actor_role   text NOT NULL,
    PRIMARY KEY (student_id, ext_id, term)
);

CREATE TABLE audit_log (
    id          bigserial PRIMARY KEY,
    actor_role  text NOT NULL,
    action      text NOT NULL,
    ext_id      text,
    before      jsonb,
    after       jsonb,
    at          timestamptz NOT NULL DEFAULT now()
);
