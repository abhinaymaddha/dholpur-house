# UPSC Interview Transcripts

Search and ask questions over UPSC Civil Services **Personality Test (interview) transcripts** that past candidates shared publicly on Telegram.

- **Keyword search** across every transcript, with filters for board, exam year and exam (CSE / IFoS), and highlighted matches.
- **Ask**: type a question, the app retrieves the most relevant transcripts and an LLM answers from them with inline citations you can open.

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
React (Vite + Tailwind)  Search · Ask · transcript reader
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
cp backend/.env.example backend/.env        # set OPENROUTER_API_KEY (and LLM_MODEL if you like)
docker compose up -d --build                # db + backend + frontend on http://localhost:8710
```

The first start loads the seed data and downloads the embedding model (~220 MB) into a volume.

## Deploy with Dokploy

1. Create a **Compose** service from this GitHub repo, compose path `./docker-compose.prod.yml`.
2. Environment:
   ```
   POSTGRES_PASSWORD=<long random string>
   OPENROUTER_API_KEY=<key>
   LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
   ADMIN_TOKEN=<long random string>        # optional, enables /api/admin/ingest
   ```
3. Domains: service `frontend`, port `80`, HTTPS on.
4. Deploy. The database seeds itself on first start; the UI shows a notice until it's ready.

Plan for about 2 GB of RAM (embedding model + Postgres).

### Choosing the LLM

`LLM_MODEL` is any OpenRouter model slug. The default is a free model (`nvidia/nemotron-3-super-120b-a12b:free`); free models are limited to 50 requests a day on accounts without credits. Stronger models (for example `anthropic/claude-sonnet-5.5`) give noticeably better answers.

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
    components/        SearchView, AskView, TranscriptPanel, ...
    services/api.ts    API client (incl. the server-sent events reader)
    lib/ hooks/ types/
docker-compose.yml       local stack (publishes :8710)
docker-compose.prod.yml  Dokploy stack (Traefik via dokploy-network)
```

## About the transcripts

The transcripts were shared publicly by candidates on Telegram, often under pseudonyms. Please respect that: don't use this project to attach real identities to them.
