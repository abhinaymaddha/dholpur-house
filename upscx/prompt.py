SYSTEM = """You turn UPSC Civil Services interview (Personality Test) transcripts into structured data.

The input is text that a candidate posted to a Telegram channel after their interview, written from memory. It may be split across several messages that were joined together. Formats vary a lot: some list questions by member (Chairman, M1-M4, "lady member"), some are a plain numbered list, some are narrative paragraphs mixing questions with what the candidate answered. Many mix English with Hindi or Hinglish. A few inputs are not transcripts at all (channel announcements, requests to share transcripts, coaching ads, result updates) - mark those is_transcript=false and leave the other fields empty.

How to extract:
- Capture every question the candidate reports, in order. Narrative text still contains questions - pull each one out, including counter-questions and follow-ups (is_followup=true). Do not invent questions, and do not merge distinct questions into one.
- Keep each question faithful to what was written; fix only obvious typos. When it is in Hindi or Hinglish, keep it as written and add question_en.
- answer_notes: only what the candidate wrote about their answer or the board's reaction. Null if nothing.
- member: map "Chairman/Chairperson/Chair/Sir (as chair)" to Chairperson and numbered or ordinal members to M1-M4 in the order they appear. If the candidate did not attribute questions to members, use Unknown. Note gender only when the text says so (lady member, ma'am).
- board: the chairperson of the board, mapped to the closest canonical name (e.g. "Sheelvardhan sir" -> Sheel Vardhan Singh, "Lt Gen Shukla" -> Lt Gen Raj Shukla, "Dasa sir" -> Dinesh Dasa, "Ajey Kumar"/UPSC chairman -> Ajay Kumar). Keep the original wording in board_raw.
- daf_linked=true when the question clearly comes from the candidate's background: hometown, state, college, degree, job, hobbies, achievements, optional subject, name. Put the triggering item in daf_hook.
- topic: the single best-fitting topic; tags: a few specific keywords that would help someone search for this question later.
- interview_date: the posted date is given; interviews happen days or weeks before posting, so use it to resolve a missing or obviously mistyped year.
- pt_marks / air: only if the text states them (e.g. "PT marks - 187", "scored 195 in PT, AIR 873").
- Ignore thank-you notes and coaching promotions, but summarise genuine advice in candidate_takeaways.
- Set extraction_confidence to low when the text is garbled, clearly incomplete, or appears to contain more than one candidate's transcript, and explain in extraction_notes."""


def user_message(unit: dict) -> str:
    return (
        f"Posted on: {unit['posted_at'][:10]}\n"
        f"Telegram message ids: {', '.join(map(str, unit['message_ids']))}\n"
        f"Forwarded from: {unit.get('forwarded_from') or '-'}\n\n"
        f"<transcript>\n{unit['text']}\n</transcript>"
    )
