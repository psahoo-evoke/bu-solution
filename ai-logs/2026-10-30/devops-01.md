# devops-01 · Azure OpenAI for the live chat ("Ask in your words")

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Agent (role) | devops |
| Tool / model | Solutionauts AI (CLI) acting as devops |
| Human owner | Sagar (spathur) |
| Trigger | User: "when im asking chat 'Ask IN YOUR Words', pls generate answers within chatbot, i have upload .env pls push code and make sure to deploy" |

## Prompt (summary)
The public chat on the live site gave no AI answers. Use the Azure OpenAI settings from the local `.env` so the chatbot answers, push and deploy.

## Finding
- `credit_chat.chat()` refuses ("The chat needs the AI service") unless `AZURE_OPENAI_ENDPOINT` is set. The live API (`bu-solutions-api`) had no `AZURE_OPENAI_*` settings; the code itself works.
- The backend does not read `.env`; `.env` is git-ignored and stays out of the repo.

## Output
- `scripts/deploy_aca.sh`: optional Azure OpenAI step (`OPENAI_ENDPOINT`, `OPENAI_DEPLOYMENT`, `OPENAI_EMBEDDING_DEPLOYMENT`, `OPENAI_KEY`). The key is stored as the Container Apps secret `openai-key` and referenced as `AZURE_OPENAI_API_KEY=secretref:openai-key`; it is never printed or committed.
- Deployed with the values from the local `.env` (only the `AZURE_OPENAI_*` ones).
- Not changed: Document Intelligence, AI Search and Postgres settings from `.env` were not applied (not needed for the chat; Postgres was already configured).

## Human review
- Pending.

## Verification
- Local API with only the `AZURE_OPENAI_*` settings: `POST /api/credit-chat` "I took Intro to Psychology PSYCH-UA 1 at NYU and got an A. Will it transfer to BU?" -> AI-written, grounded reply (`grounded: true`, 1 rules-engine result).
- `bash -n scripts/deploy_aca.sh`: OK. Live check after deploy: see the commit message / session.

## Commit
See git log (`devops: Azure OpenAI settings for the live chat in deploy_aca.sh (devops-01)`).
