"""A small synthetic Telegram export (messages.html + messages2.html) covering the cases ingest handles:
several boards and years, DAF and optional lines, PT marks, contact details to redact, a repost that
must be de-duplicated, an admin request that must be held, and a forwarded notice that is noise."""

from __future__ import annotations

import html
from pathlib import Path

RAJASTHAN = """Name - Mr. X (07/01 AN)
Key words of DAF - trekking, cricket, electrical engineering, economics, Rajasthan, power distribution
Board - Sheel Vardhan sir
Optional - Economics

Chairman
Where have you trekked and what have you learnt from trekking?
What is the difference between an environment activist and a climate activist?
What problems have you seen during trekking in the Himalayas?
Why should a district collector care about forest fires?

Member 1
Why did you choose economics as optional when you have done electrical engineering?
How can you link electrical efficiency and economic efficiency?
What is a neural network and how can it be used in economics?

Member 2
What is the per capita GDP of India and why is manufacturing lagging?
Can India skip manufacturing and move straight to services?
What steps should be taken to boost manufacturing in Rajasthan?

Member 3
Is hydro energy clean energy, and which form of energy is the cleanest?
What is the solar energy policy of Rajasthan?
What would you do as DM of a drought-hit district in Rajasthan?

Member 4 (mam)
Why civil services after engineering?
What three policy initiatives would you take for public health?
How do you see India's relations with China on the border?
"""

HARYANA = """Name - Static
Interview- 08/01/2025
Board - Sanjay verma
DAF - Haryana , IIT BHU Varanasi, IOCL , Chemical Engg., Bhagwad Geeta
Opt - math

Chairman
How many web series have you watched and which was the best?
Why do you read the Gita and when did you start it?
What is your understanding of dharma in public life?

M1
Is ancient Indian society dharma based or caste based?
What are the ethical dilemmas a refinery engineer faces?
Suppose your senior asks you to sign a false safety report, what will you do?

M2 ( female member )
What is the difference between karma, bhakti and sankhya yoga?
What are the three gunas and how do they shape a civil servant's character?
Why is integrity more important than competence in administration?

M3
With economic growth, inequality is rising in India. Why?
What would you do as DM of a flood-hit district in Haryana?
How should India balance its relations with the USA and Russia?
What is the role of the RBI in controlling inflation?
"""

KERALA = """Name - Dr. Y
Date of interview - 12/02/2024
DAF - Kerala, MBBS, Government Medical College, Sociology, reading novels
Board - Sujata ma'am
Optional - Sociology
PT marks - 182

Chairperson
Why did you leave medicine for the civil services?
How would you fix the shortage of doctors in rural hospitals?
What is your view on the mental health crisis among students?

Member 1
How has the Kerala model of health care worked, and where has it failed?
What are the causes of malnutrition among tribal children?
What should be done about the brain drain of nurses from Kerala?

Member 2
Why is female labour force participation low in India?
How does caste still affect access to education in villages?
What is the role of women self help groups in rural development?

Member 3
Which novels have you read recently and what did you learn from them?
How can schools teach values without preaching?
What would you do if a hospital in your district denied treatment to a poor patient?

Thank you all.
Write to me: candidate.y@example.org or +91 9000012345
"""

BIHAR = """Name - Z
Interview date - 18/03/2025
Key words - Bihar, B.A. History, Delhi University, teaching, chess
Board - Raj Shukla sir
Optional - History

Chairman
What is the significance of Nalanda university in Indian history?
How did the Champaran satyagraha change the freedom struggle?
Why is Bihar still lagging in industrial growth?

Member 1
What is the role of the army in disaster relief operations?
How should India deal with left wing extremism in Bihar?
Is the Agniveer scheme good for the armed forces?

Member 2
Why is chess popular in India now, and who are the top players?
What did teaching in a school teach you about governance?
How can migration from Bihar be reduced?

Member 3
What are the challenges of internal security on the Nepal border?
How do you see the rise of cyber crime in rural areas?
What is the role of the police in preventing communal riots?
"""

ADMIN_REQUEST = ("Hello people,\nYou are requested to share your interview transcripts of CSPT 2025 in this group. "
                 "Please mention board, date and DAF keywords. " + "Thanks. " * 80)

NOTICE = "UPSC has released the interview schedule for the next phase. Check the official website for details."

# (id, posted_at title, text, forwarded_from, reactions)
MESSAGES = [
    (10, "10 January 2025, 17:27:51", RAJASTHAN, None, 36),
    (11, "11 January 2025, 09:02:10", HARYANA, None, 12),
    (12, "12 January 2025, 08:00:00", ADMIN_REQUEST, None, 0),
    (13, "13 January 2025, 10:30:00", NOTICE, "CSE Updates", 0),
    (14, "14 February 2024, 18:45:12", KERALA, None, 20),
]
MESSAGES_PAGE2 = [
    (20, "20 March 2025, 21:15:00", BIHAR, None, 8),
    (21, "25 March 2025, 11:00:00", HARYANA + "\nPT marks - 187", None, 30),   # repost with marks: keeps this one
]


def _message(mid: int, title: str, text: str, fwd: str | None, reactions: int) -> str:
    body = html.escape(text).replace("\n", "<br>")
    fwd_html = f'<div class="forwarded_from">Forwarded from {html.escape(fwd)}</div>' if fwd else ""
    react = (f'<div class="reactions"><span class="reaction"><span class="emoji">👍</span>'
             f'<span class="count">{reactions}</span></span></div>') if reactions else ""
    return (f'<div class="message default clearfix" id="message{mid}"><div class="body">'
            f'<div class="pull_right date details" title="{title}">00:00</div>'
            f'<div class="from_name">Interview Transcripts (CSPT-2026)</div>{fwd_html}'
            f'<div class="text">{body}</div>{react}</div></div>')


def _page(messages: list[tuple]) -> str:
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><div class="history">'
            '<div class="message service" id="message1"><div class="body details">10 January 2025</div></div>'
            + "".join(_message(*m) for m in messages) + "</div></body></html>")


def write_export(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "messages.html").write_text(_page(MESSAGES), encoding="utf-8")
    (folder / "messages2.html").write_text(_page(MESSAGES_PAGE2), encoding="utf-8")
    return folder
