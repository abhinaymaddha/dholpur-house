# Contributing to Dholpur House

Thank you for wanting to help candidates prepare for the Personality Test. Contributions of every
size are welcome: bug reports, better prompts, new interview topics, fixes, features and
documentation.

Please read the [Disclaimer](DISCLAIMER.md) and [DATA.md](DATA.md) first. In short: this is an
independent, non-commercial project, and the transcripts belong to their authors.

## Ways to contribute

- **Report a bug or suggest an idea**: open an
  [issue](https://github.com/abhinaymaddha/dholpur-house/issues). For bugs, include what you did,
  what you expected and what happened (a screenshot helps).
- **Improve interview prompts**: the prompts live in `backend/app/interview/prompts/`, one file per
  topic plus the question and evaluation templates. See "Changing prompts" below.
- **Add a current-affairs source**: add an RSS or Atom feed to `backend/sources.toml`.
- **Fix or build something**: comment on an issue first (or open one) for anything larger than a
  small fix, so we can agree on the approach before you spend time on it.
- **Content concerns**: to have a transcript removed or corrected, open an issue. Please don't send
  pull requests that edit `backend/seed/` directly.

## Setting up

You need Python 3.14, Node 26 and Postgres 17 with the pgvector extension. No API key is needed to run the
tests; only Ask AI and generated interview questions need one to run the app (see
[Choose your AI model](README.md#choose-your-ai-model)).

```bash
# backend
cd backend
python3.14 -m venv .venv && source .venv/bin/activate
make install
docker compose up -d db                     # from the repo root, or point DATABASE_URL at any Postgres with pgvector
python -m app.ingest --seed                 # load the transcripts that ship with the repo (10-15 min)
make dev                                    # API on http://localhost:8000

# frontend
cd frontend
npm install
npm run dev                                 # http://localhost:5173, forwards /api to :8000
```

Once both are set up, `./scripts/dev.sh` starts the API and the frontend together with auto-reload.

On macOS without Docker, Postgres can come from Homebrew:

```bash
brew install postgresql@17 pgvector python@3.14 && brew services start postgresql@17
psql -d postgres -c "CREATE ROLE upsc LOGIN PASSWORD 'upsc'" -c "CREATE DATABASE upsc OWNER upsc"
psql -d upsc -c "CREATE EXTENSION vector"
```

### Tests

- **Backend** (`cd backend && make test`): pytest against a real Postgres + pgvector database. The suite loads a
  small synthetic Telegram export (`tests/fixtures/export.py`) through the real ingest pipeline, and replaces the
  embedding model with a deterministic stand-in and every AI call with a scripted fake, so it needs no model
  download, network or API key. It uses `TEST_DATABASE_URL` (default
  `postgresql://upsc:upsc@localhost:5432/upsc_test`); create that database once with
  `psql -d postgres -c "CREATE DATABASE upsc_test OWNER upsc"` and `psql -d upsc_test -c "CREATE EXTENSION vector"`.
  The tests drop and recreate its tables, so never point it at real data. Coverage below 95% fails.
- **Frontend** (`cd frontend && npm test`, or `npm run test:coverage`): vitest and Testing Library, with the API
  client mocked. Coverage thresholds are in `vitest.config.ts`.

### How the code is organised

```
backend/
  app/
    main.py            FastAPI app, error handler, startup (schema, first-start data load, warm-ups)
    config.py          settings from the environment / .env
    dependencies.py    shared repository and service instances for routes (overridable in tests)
    errors.py          AppError hierarchy, mapped to HTTP status codes
    api/routes/        search, transcripts, stats, ask, interview, admin, health
    repositories/      all SQL: transcripts, sections, questions, interviews, news
    llm/               LLMProvider base class and the OpenAI-compatible, OpenAI, OpenRouter and Anthropic providers
    services/          hybrid retrieval, news feeds, Ask answers, embeddings, rate limits, ingest jobs
    interview/         InterviewSession, question sources (generated / real), evaluator, prompts/
    ingest/            Telegram export to Postgres: parse, segment, classify, tag, redact, embed
  seed/                the channel's messages (JSONL), loaded on first start
  models.toml          AI providers and model slots
  sources.toml         current-affairs feeds (RSS/Atom)
  prompt_eval/         prompt test cases and runner
  tests/               unit and integration tests; fixtures (synthetic export, fakes)
frontend/src/
  components/          Browse, Ask AI, Interview, transcript reader, ...
  services/api.ts      API client, including the server-sent events reader for Ask AI
  lib/ hooks/ types/ test/
```

### Interview topics and prompts

Each topic is a file in `backend/app/interview/prompts/topics/`. Its header says whether the topic draws on
current affairs (`news: yes`) or needs the candidate's DAF (`daf: required`); the body is the guidance the
question writer and the evaluator see. `question.md`, `question_daf.md` and `evaluate.md` are the templates.
Prompt files are read on every call, so you can edit and retry without restarting. The follow-up rules are in
`app/interview/session.py`.

### Adding an AI provider

Most providers work through `openai_compatible` in `models.toml`. For one with its own API, subclass
`LLMProvider` (`backend/app/llm/base.py`), implement `complete_json` and `stream_text`, give it a `kind`, and
register it with `@register` from `app.llm.registry`. `OpenRouterProvider` is a small example that only
overrides a few hooks.

## Before you open a pull request

1. **Run the tests.** Both suites must pass, and coverage must not drop:
   ```bash
   cd backend && make test                       # needs the upsc_test database, see Tests above
   cd frontend && npm run lint && npm run test:coverage && npm run build
   ```
   CI runs the same checks on every pull request.
2. **Add tests for what you change.** Backend tests use the synthetic export in
   `backend/tests/fixtures/` and fake embeddings and LLM providers, so they need no network or keys.
   Frontend tests sit next to the component as `*.test.tsx` and mock the API client.
3. **Keep the structure.**
   - All SQL lives in `backend/app/repositories/`.
   - New LLM providers subclass `LLMProvider` and are registered in `app/llm/registry.py`.
   - Routes get repositories and services through `app/dependencies.py`.
   - Errors meant for users are `AppError` subclasses from `app/errors.py`.
   - Follow the style of the surrounding code; the frontend uses the theme colours in
     `frontend/src/index.css` (stone, sandstone, brass, lawn, teak, iron) rather than raw Tailwind
     palettes.
4. **Never commit secrets or personal data.** API keys belong in `backend/.env`, which is ignored.
   Don't add anyone's email address, phone number or other contact details, including in tests.
5. **Write a clear description**: what changed, why, and how you tested it.

## Changing prompts

Prompt quality matters more than anything else in Interview mode, so measure changes rather than
guess:

```bash
cd backend
python -m prompt_eval.run evaluator        # each evaluator case, with its expected verdict
python -m prompt_eval.run questions        # sample generated questions per case
```

Add a case to `prompt_eval/evaluator_cases.json` or `question_cases.json` when you fix a problem,
and include the before and after results in your pull request. The evaluator must stay
**critical but fair, and must never invent facts**. The code guards in
`app/interview/evaluator.py` exist for that reason, so please don't weaken them.

## Licence of contributions

The project is licensed under [CC BY-NC 4.0](LICENSE). By submitting a contribution, you agree
that it is licensed under the same terms. The interview transcripts are not covered by this
licence; see [DATA.md](DATA.md).

## Conduct

Be kind and constructive. Many people using this project are preparing for one of the most
important interviews of their lives; please keep discussions respectful and helpful.
