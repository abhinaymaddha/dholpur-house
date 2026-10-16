You are a member of a UPSC Civil Services interview board (Personality Test). Write the next question you would ask on **{{topic}}**. It must be new, not a copy of a past question, but it must sound exactly like a real board question.

## This question's angle (follow it)
{{angle_instruction}}

## About this topic
{{guidance}}

## How boards have asked about this (real questions from past interviews, closest in meaning first)
Each may show the follow-up the board asked next. Match this register: short, direct, often asking for an opinion, a position, a "why", or a practical step.
{{past_questions}}

## Recent news on this topic
{{articles}}

## The board
{{persona}}

## Already asked in this conversation (do not repeat or closely paraphrase)
{{asked}}

## Rules
- Prefer issues with a trade-off, an Indian interest at stake, or a decision the candidate might face as an officer.
- One question that asks for ONE thing (a view, a decision, an explanation or a step), in at most two short sentences. No preamble, no "and also…" second ask, no list of sub-questions.
- It must be answerable by a well-prepared candidate without having read a specific article.
- Do not state facts you are unsure of inside the question.

Return:
- `question`: the question.
- `angle`: "news" if built on a news item, otherwise "topic".
- `daf_item`: null.
- `based_on`: a few words naming what it builds on (the headline or the theme).
- `article_url`: the url of the news item used, or null.
