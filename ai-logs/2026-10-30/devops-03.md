# devops-03 · Sample backend configuration (.env.example)

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | devops |
| Tool / model | Solutionauts AI (Claude Code) |
| Human owner | Team lead |
| Trigger | "backend/.env.example fix it and commit" (scorecard 3.1: sample config) |

## Prompt (summary or verbatim)
Fix the untracked `backend/.env.example` and commit it.

## Inputs used
- The draft `backend/.env.example` (copied from the local `.env`), every `os.environ.get` in `backend/app/`

## Output
- `backend/.env.example` rewritten: all 41 settings the backend reads, grouped by service, each with its default and what happens when it is unset
- Fixed in the draft: a broken line (`AZURE_OPENAI_EMBEDDING_DEPLOYMENTe`, no `=`), a header saying the file must never be committed, a stray model-name comment, the real database user name
- Design: everything optional is commented out, because an empty value is not "unset" for some settings (empty `TRANSFERIQ_AUTH_MODE` is not demo mode, empty `TRANSFERIQ_DEMO_PASSWORD` is an empty password, empty `TRANSFERIQ_SEED_DIR` breaks loading). Copied as is, the app runs offline in demo mode.
- `README.md` §7 points to the file and shows how to load it

## Human review
- Team lead asked for the fix and the commit.

## Verification
- Every environment variable read in `backend/app/*.py` appears in the file
- Clean environment, `set -a; source .env.example`: auth mode demo, engine offline-fallback, PostgreSQL off, `GET /api/health` 200
- No real hostnames, user names or keys in the file; the file is not gitignored

## Commit
See `git log -- backend/.env.example`
