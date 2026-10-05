"""JSON schema for one extracted transcript (used as output_config.format)."""

BOARDS = [
    "Sanjay Verma", "Dinesh Dasa", "Suman Sharma", "Sheel Vardhan Singh", "Lt Gen Raj Shukla",
    "BB Swain", "Sujata Chaturvedi", "Anuradha Prasad", "Preeti Sudan", "Ajay Kumar",
    "Other", "Unknown",
]

TOPICS = [
    "Polity & Constitution", "Governance & Administration", "International Relations",
    "Economy", "Agriculture & Rural", "Society & Social Justice", "Education", "Health",
    "History & Culture", "Geography & Environment", "Science & Technology",
    "Internal Security & Defence", "Ethics & Integrity", "Situational / Hypothetical",
    "Optional Subject", "Academic Background", "Work Experience", "Hobbies & Interests",
    "Hometown & State", "Sports", "Personal & Motivation", "Current Affairs (other)", "Other",
]

MEMBERS = ["Chairperson", "M1", "M2", "M3", "M4", "Unknown"]

_str = {"type": ["string", "null"]}
_int = {"type": ["integer", "null"]}
_strs = {"type": "array", "items": {"type": "string"}}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


QUESTION = _obj({
    "seq": {"type": "integer", "description": "1-based order within the interview"},
    "member": {"type": "string", "enum": MEMBERS},
    "member_gender": {"type": "string", "enum": ["male", "female", "unknown"]},
    "question": {"type": "string", "description": "The question as asked, cleaned up but faithful. Keep Hindi/Hinglish as written."},
    "question_en": _str | {"description": "English rendering if the question is not in English, else null"},
    "answer_notes": _str | {"description": "What the candidate said they answered or how it went, if written; else null"},
    "is_followup": {"type": "boolean", "description": "Follow-up/counter on the previous question"},
    "daf_linked": {"type": "boolean", "description": "Triggered by the candidate's DAF/background"},
    "daf_hook": _str | {"description": "Which DAF item triggered it (e.g. 'hometown Vidisha', 'hobby: chess'), else null"},
    "topic": {"type": "string", "enum": TOPICS},
    "tags": _strs | {"description": "2-5 short specific tags, e.g. ['Bangladesh', 'neighbourhood first']"},
})

TRANSCRIPT = _obj({
    "is_transcript": {"type": "boolean", "description": "False for announcements, requests, ads, results, or chatter"},
    "non_transcript_kind": _str | {"description": "If not a transcript: 'announcement', 'request', 'ad', 'results', 'advice', 'other'"},
    "exam": {"type": "string", "enum": ["CSE", "IFoS", "Other", "Unknown"]},
    "alias": _str | {"description": "Name or pseudonym the candidate gave"},
    "interview_date": _str | {"description": "YYYY-MM-DD; infer the year from the posted date when omitted"},
    "session": {"type": "string", "enum": ["FN", "AN", "Unknown"]},
    "order_in_session": _int | {"description": "e.g. 'third to go' -> 3; 'last' -> null"},
    "board_raw": _str,
    "board": {"type": "string", "enum": BOARDS},
    "duration_minutes": _int | {"description": "Midpoint if a range is given"},
    "optional_subject": _str,
    "home_state": _str,
    "hometown": _str,
    "education": _strs | {"description": "Degrees with field and institution, e.g. 'B.Tech Chemical, IIT BHU'"},
    "work_experience": _strs,
    "current_service": _str | {"description": "If already in a service/job via exams (e.g. IRS-IT, ASO), else null"},
    "hobbies": _strs,
    "daf_keywords": _strs | {"description": "All DAF keywords the candidate listed"},
    "daf_items_not_asked": _strs | {"description": "DAF items the candidate says were NOT asked"},
    "pt_marks": _int | {"description": "Personality test marks out of 275 if stated"},
    "air": _int | {"description": "All India Rank if stated"},
    "mocks": _strs | {"description": "Mock interview providers / mentors mentioned"},
    "board_behaviour": _str | {"description": "1-2 sentences on tone and style (cordial, grilling, DAF-heavy, monologues...)"},
    "candidate_takeaways": _str | {"description": "Advice or reflections the candidate shared, condensed"},
    "questions": {"type": "array", "items": QUESTION},
    "extraction_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "extraction_notes": _str | {"description": "Anything ambiguous: merged posts, missing parts, unclear member mapping"},
})
