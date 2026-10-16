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

Follow [Develop](README.md#develop) in the README. You need Python 3.12, Node 24 and Postgres 17
with pgvector. No API key is needed to run the tests, and only Ask AI and generated interview
questions need one to run the app (see [Bring your own model](README.md#bring-your-own-model)).

## Before you open a pull request

1. **Run the tests.** Both suites must pass, and coverage must not drop:
   ```bash
   cd backend && make test                       # needs the upsc_test database, see README → Tests
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
