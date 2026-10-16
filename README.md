# Dholpur House

Prepare for the UPSC Civil Services **Personality Test** (the interview, held at Dholpur House, New Delhi) with the real transcripts past candidates shared on Telegram: search them, ask questions about them, and practise with an AI interview board that asks, listens and critiques.

- **Browse**: keyword search across every transcript, combined with drill-down by exam year → board and tags (background, optional, home state, interests, topics asked); highlighted matches and a formatted reader.
- **Ask AI** (in Browse): ask a question and an LLM answers from the transcripts matching your current search and filters, with inline citations you can open.
- **Interview**: practise with an AI board. Pick topics and add your DAF; the board writes new questions from your DAF, recent news and the most similar real questions from past interviews (or, with a toggle, asks real past questions only). Every answer is evaluated critically; a good answer earns up to two follow-ups. Coach mode shows feedback after each answer (and a "How have boards asked this?" helper with similar moments from real transcripts); Exam mode only in the end report.

> Transcripts are candidates' own recollections. Answers are generated from them and can be wrong, so always check the cited sources.

## Data credit

All interview transcripts come from the public Telegram channel
**[Interview Transcripts (CSPT-2026)](https://t.me/csetranscripts)** (@csetranscripts). Full credit goes to the
channel's admins and to the candidates who shared their experiences. This project only makes them searchable and
claims no ownership. If you are the channel admin or an author and want any of it removed, please
[open an issue](https://github.com/abhinaymaddha/dholpur-house/issues) or contact @abhinaymaddha on GitHub and it will be
removed. Details in [DATA.md](DATA.md).

## How it works

```
Telegram Desktop export (messages.html)
   │  backend/app/ingest
   ├─ parse      one record per message
   ├─ segment    join transcripts split by Telegram's 4096-char limit, drop channel noise,
   │             remove reposts (kept: the longest copy)
   ├─ classify   accept clearly marked transcripts (header + questions); hold the rest
   ├─ metadata   board, alias, date, DAF, optional, PT marks (rules, no LLM)
   └─ chunk      split each transcript at member sections (Chairman / M1 / ...) and embed locally
   ▼
Postgres + pgvector
   ├─ transcripts  full text + tsvector (keyword search)
   ├─ chunks       section text + tsvector + 384-d embedding (RAG retrieval)
   └─ held         units not loaded as transcripts, with the reason
   ▼
FastAPI  /api/search  /api/transcripts/{id}  /api/stats  /api/ask (server-sent events)
   ▼
React (Vite + Tailwind)  Browse (search + filters + Ask AI) · Interview · transcript reader
```

**Retrieval for Ask** runs vector similarity and full-text match over chunks, fuses the two rankings (reciprocal rank fusion), groups by transcript, and sends the top transcripts' best sections to the LLM you configure (see [Bring your own model](#bring-your-own-model)). Embeddings are computed locally with [fastembed](https://github.com/qdrant/fastembed) (`paraphrase-multilingual-MiniLM-L12-v2`, handles Hindi), so only answer generation needs an API key.

## Data

`backend/seed/csetranscripts_messages.jsonl` holds every message from the public Telegram channel
[@csetranscripts](https://t.me/csetranscripts) (text only, one JSON object per message, emails and phone numbers
removed; see [DATA.md](DATA.md)). On first start, when the
database is empty, the backend loads it automatically (a few minutes: transcripts are parsed and embedded).

To load a newer export:

- **CLI:** `python -m app.ingest "<ChatExport folder>"` (or `--write-seed "<folder>"` to refresh the committed seed).
- **HTTP** (set `ADMIN_TOKEN` first; no shell access needed on a hosted server):
  ```bash
  curl -H "Authorization: Bearer $ADMIN_TOKEN" -F "files=@messages.html" https://<host>/api/admin/ingest
  curl -H "Authorization: Bearer $ADMIN_TOKEN" https://<host>/api/admin/ingest     # progress
  ```

Make an export in Telegram Desktop: channel → ⋮ → Export chat history → format HTML, media not needed.
Every ingest replaces all data with the given messages.

## Run it locally

Requirements: Docker with Compose, and an API key for an LLM provider (OpenRouter, OpenAI, Anthropic, or any
OpenAI-compatible server; a local Ollama needs no key).

```bash
cp backend/.env.example backend/.env        # put your provider's API key in it
# optional: edit backend/models.toml to choose provider and models (default: a free OpenRouter model)
docker compose up -d --build                # db + backend + frontend on http://localhost:8710
```

The first start loads the seed data (about 12 minutes on a laptop CPU: every transcript section and every question is
embedded) and downloads the embedding model (~220 MB) into a volume.

## Deploy with Dokploy

1. Create a **Compose** service from this GitHub repo, compose path `./docker-compose.prod.yml`.
2. Environment:
   ```
   POSTGRES_PASSWORD=<long random string>
   OPENROUTER_API_KEY=<key>                # or OPENAI_API_KEY / ANTHROPIC_API_KEY, matching models.toml
   ADMIN_TOKEN=<long random string>        # optional, enables /api/admin/ingest
   ```
3. Domains: service `frontend`, port `80`, HTTPS on.
4. Deploy. The database seeds itself on first start; the UI shows a notice until it's ready.

Plan for about 2 GB of RAM (embedding model + Postgres).

## Bring your own model

Everything about which LLM is used lives in **`backend/models.toml`**:

- **`[providers.*]`**: where requests go. `kind` is `openrouter`, `openai`, `anthropic` (official Claude SDK) or
  `openai_compatible` (Groq, Together, DeepSeek, Mistral, Gemini's OpenAI endpoint, Ollama, vLLM, LM Studio, …),
  plus `base_url` and the environment variable holding the key (`api_key_env`). For a private local setup you can
  put the key inline as `api_key` instead (don't commit it).
- **`[models.model_1|2|3]`**: the slot each part of the app uses, pointing at a provider and a model id:

| Slot | Used for |
|---|---|
| `model_1` | Ask AI (Browse): answers from retrieved transcripts |
| `model_2` | Interview: writes new questions |
| `model_3` | Interview: critical evaluation of each answer and follow-up questions |

Switching, for example, the evaluator to Claude:

```toml
[models.model_3]
provider = "anthropic"
id = "claude-opus-5-5"
reasoning_effort = "medium"
fallbacks = "default"        # let the Claude API retry a declined request on a fallback model
```

and set `ANTHROPIC_API_KEY` in `backend/.env`. The file is re-read on change; no restart needed. If a provider has
no JSON-schema support, set `json_mode = "object"` (or `"prompt"`) on the slot. The shipped default is a free
OpenRouter model (limited to 50 requests a day on accounts without credits); the evaluator in particular benefits from
a stronger model.

A provider with its own API can be added in code: subclass `LLMProvider` (`backend/app/llm/base.py`), implement
`complete_json` and `stream_text`, give it a `kind`, and register it with `@register` from `app.llm.registry`
(see `OpenRouterProvider` for a small example that only overrides a few hooks).

## Interview mode

- **How questions are made (default):** for each question, `model_2` gets the topic guidance, your DAF, the chosen
  board's style, recent articles (for news topics), about 15 real past questions closest in meaning to the topic,
  your DAF and the headlines (each with the follow-up the board asked next), and the full question lists of two
  candidates whose profile best matches your DAF. It writes one new question in that style
  (`prompts/question.md`).
- **Real past questions only:** a toggle that skips generation and asks the closest real questions directly; no LLM call.
- **Question search:** every question from every transcript is embedded at ingest (`questions.embedding`), so "similar
  questions" means similar in meaning, not just sharing a tag. Profile and board stay transcript-level tags.
- **Topics and prompts:** `backend/app/interview/prompts/topics/*.md`, one file per topic. The header says whether the
  topic uses current affairs (`news: yes`) or needs the DAF (`daf: required`); the body is the guidance the question
  writer and evaluator see. `question.md` and `evaluate.md` are the templates. Prompt files are read on every call:
  edit and try again, no restart.
- **Current affairs:** `backend/sources.toml` lists RSS/Atom feeds. Articles are tagged with topics by the same rules
  as transcripts and refreshed every few hours (or `POST /api/admin/news/refresh`).
- **Rules (in code, `app/interview/engine.py`):** an answer is "good" only if every score is at least 3 and the average
  at least 3.5; good answers get up to two follow-ups, anything else gets critique and the next question. Each answer
  costs one LLM call (`model_3`); follow-up examples come from the real questions most similar to the one asked.

## Develop

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
make install
docker compose up -d db                     # from the repo root, or point DATABASE_URL at any Postgres with pgvector
make dev                                    # API on :8000
make test

# frontend
cd frontend
npm install
npm run dev                                 # http://localhost:5173, proxies /api to :8000
```

Or, once both are set up, `./scripts/dev.sh` runs the API and the frontend together with auto-reload.

### Tests

Both halves are fully tested, and CI (`.github/workflows/ci.yml`) runs everything on every push.

- **Backend** (`cd backend && make test`): pytest against a real Postgres + pgvector database. The suite
  ingests a small synthetic Telegram export (`tests/fixtures/export.py`) through the real pipeline, swaps the
  embedding model for a deterministic stand-in and every LLM call for a scripted fake provider, so it needs no
  model download, network or API key. It uses `TEST_DATABASE_URL`
  (default `postgresql://upsc:upsc@localhost:5432/upsc_test`; create it with
  `psql -d postgres -c "CREATE DATABASE upsc_test OWNER upsc"` and `psql -d upsc_test -c "CREATE EXTENSION vector"`).
  The tests drop and recreate the tables in that database, so never point it at real data. Coverage below 95% fails.
- **Frontend** (`cd frontend && npm test`, or `npm run test:coverage`): vitest + Testing Library with the API
  client mocked. Coverage thresholds live in `vitest.config.ts`.

On macOS without Docker, Postgres can come from Homebrew:

```bash
brew install postgresql@17 pgvector python@3.12 && brew services start postgresql@17
psql -d postgres -c "CREATE ROLE upsc LOGIN PASSWORD 'upsc'" -c "CREATE DATABASE upsc OWNER upsc"
psql -d upsc -c "CREATE EXTENSION vector"
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m app.ingest --seed       # load the committed data (~5 min)
```

## Repository layout

```
backend/
  app/
    main.py            FastAPI app, error handler, startup (schema, seeding, warm-ups)
    config.py          settings from environment / .env
    database.py        connection pool + schema
    dependencies.py    shared repository/service instances for routes (overridable in tests)
    errors.py          AppError hierarchy → HTTP status codes
    api/routes/        search, transcripts, stats, ask, interview, admin, health
    schemas/           response and request models
    repositories/      all SQL: transcripts, chunks, questions, interviews, news
    llm/               LLMProvider base + OpenAI-compatible, OpenAI, OpenRouter, Anthropic; registry
    services/          HybridRetriever, NewsService, Ask answers, embeddings, ingest jobs
    interview/         InterviewSession, QuestionSource (generated / real), evaluator, prompts/
    ingest/            Telegram export → Postgres
  seed/                committed channel messages (JSONL), loaded on first start
  models.toml          LLM providers and model slots
  sources.toml         current-affairs feeds
  prompt_eval/         prompt test cases + runner
  tests/               unit + integration tests, fixtures (synthetic export, fakes)
frontend/
  src/
    components/        BrowseView, AskPanel, interview/, TranscriptPanel, ...
    services/api.ts    API client (incl. the server-sent events reader)
    lib/ hooks/ types/
    test/              test setup and fixtures (tests sit next to the code as *.test.tsx)
.github/workflows/ci.yml   backend + frontend tests on every push
docker-compose.yml       local stack (publishes :8710)
docker-compose.prod.yml  Dokploy stack (Traefik via dokploy-network)
```

## License

Code, prompts and docs: [CC BY-NC 4.0](LICENSE). Free to use, share and adapt for non-commercial purposes, with
credit. **Commercial use needs permission:** [open an issue](https://github.com/abhinaymaddha/dholpur-house/issues) or
contact @abhinaymaddha on GitHub.

The transcripts are not covered by this license; they belong to their authors (see [Data credit](#data-credit) and
[DATA.md](DATA.md)). Candidates often posted under pseudonyms: please don't use this project to attach real identities
to them.
