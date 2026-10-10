# UPSC Interview Transcripts

Search and ask questions over UPSC Civil Services **Personality Test (interview) transcripts** that past candidates shared publicly on Telegram.

- **Browse**: keyword search across every transcript, combined with drill-down by exam year → board and tags (background, optional, home state, interests, topics asked); highlighted matches and a formatted reader.
- **Ask**: type a question, the app retrieves the most relevant transcripts and an LLM answers from them with inline citations you can open.
- **Interview**: practise with an AI board. Pick topics; questions come from real past interviews or, for news-heavy topics, from current affairs. Every answer is evaluated critically; a good answer earns up to two follow-ups. Coach mode shows feedback after each answer, Exam mode only in the end report.

> Transcripts are candidates' own recollections. Answers are generated from them and can be wrong, so always check the cited sources.

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
React (Vite + Tailwind)  Browse (search + filters) · Ask · Interview · transcript reader
```

**Retrieval for Ask** runs vector similarity and full-text match over chunks, fuses the two rankings (reciprocal rank fusion), groups by transcript, and sends the top transcripts' best sections to the LLM via [OpenRouter](https://openrouter.ai). Embeddings are computed locally with [fastembed](https://github.com/qdrant/fastembed) (`paraphrase-multilingual-MiniLM-L12-v2`, handles Hindi), so only answer generation needs an API key.

## Data

`backend/seed/csetranscripts_messages.jsonl` holds every message from the public Telegram channel
[@csetranscripts](https://t.me/csetranscripts) (text only, one JSON object per message). On first start, when the
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

Requirements: Docker with Compose, and an [OpenRouter API key](https://openrouter.ai/keys).

```bash
cp backend/.env.example backend/.env        # set OPENROUTER_API_KEY
docker compose up -d --build                # db + backend + frontend on http://localhost:8710
```

The first start loads the seed data and downloads the embedding model (~220 MB) into a volume.

## Deploy with Dokploy

1. Create a **Compose** service from this GitHub repo, compose path `./docker-compose.prod.yml`.
2. Environment:
   ```
   POSTGRES_PASSWORD=<long random string>
   OPENROUTER_API_KEY=<key>
   ADMIN_TOKEN=<long random string>        # optional, enables /api/admin/ingest
   ```
3. Domains: service `frontend`, port `80`, HTTPS on.
4. Deploy. The database seeds itself on first start; the UI shows a notice until it's ready.

Plan for about 2 GB of RAM (embedding model + Postgres).

### Models

All LLM calls go through OpenRouter. `backend/models.toml` defines numbered slots, and code refers only to the slot:

| Slot | Used for |
|---|---|
| `model_1` | Ask: answers from retrieved transcripts |
| `model_2` | Interview: new questions from current affairs or the candidate's DAF |
| `model_3` | Interview: critical evaluation of each answer and follow-up questions |

Change a model id there and every flow using that slot switches; the file is re-read on change. The defaults are a
free model, limited to 50 requests a day on accounts without credits; the evaluator in particular benefits from a stronger model.

## Interview mode

- **Topics and prompts:** `backend/app/interview/prompts/topics/*.md`, one file per topic. The header sets where
  questions come from (`past`, `current`, `mixed` with `current_share`, or `daf`); the body is the guidance the
  question writer and evaluator see. `question_current.md`, `question_daf.md` and `evaluate.md` are the templates.
  Every call adds real questions from past transcripts on that topic (and the chosen board's style), so prompts stay
  grounded in how boards actually ask. Prompt files are read on every call: edit and try again, no restart.
- **Current affairs:** `backend/sources.toml` lists RSS/Atom feeds. Articles are tagged with topics by the same rules
  as transcripts and refreshed every few hours (or `POST /api/admin/news/refresh`).
- **Rules (in code, `app/interview/engine.py`):** an answer is "good" only if every score is at least 3 and the average
  at least 3.5; good answers get up to two follow-ups, anything else gets critique and the next question. Past
  questions are drawn without an LLM call; each answer costs one call.

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
    main.py            FastAPI app
    config.py          settings from environment / .env
    database.py        connection pool + schema
    api/routes/        search, transcripts, stats, ask, health
    schemas/           response and request models
    services/          search, retrieval, llm, embeddings
    ingest/            Telegram export → Postgres
  seed/                committed channel messages (JSONL), loaded on first start
  tests/
frontend/
  src/
    components/        BrowseView, AskView, interview/, TranscriptPanel, ...
    services/api.ts    API client (incl. the server-sent events reader)
    lib/ hooks/ types/
docker-compose.yml       local stack (publishes :8710)
docker-compose.prod.yml  Dokploy stack (Traefik via dokploy-network)
```

## About the transcripts

The transcripts were shared publicly by candidates on Telegram, often under pseudonyms. Please respect that: don't use this project to attach real identities to them.
