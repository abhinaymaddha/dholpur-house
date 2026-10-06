"""Telegram Desktop HTML export -> one dict per message, text untouched."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup



def _text(div) -> str:
    if div is None:
        return ""
    for br in div.find_all("br"):
        br.replace_with("\n")
    return div.get_text().strip()


def parse_export(export_dir: Path) -> list[dict]:
    pages = sorted(export_dir.glob("messages*.html"), key=lambda p: (len(p.name), p.name))
    rows = []
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "lxml")
        for div in soup.select("div.message.default"):
            body = div.find("div", class_="body", recursive=False)
            date = body.find("div", class_="date")
            fwd = body.find("div", class_="forwarded_from")
            # Forwarded messages nest their text one level deeper, so fall back to a deep search.
            text_div = body.find("div", class_="text", recursive=False) or body.find("div", class_="text")
            posted = datetime.strptime(date["title"].split(" UTC")[0], "%d %B %Y, %H:%M:%S") if date else None
            rows.append({
                "id": int(div["id"][len("message"):]),
                "posted_at": posted.isoformat() if posted else None,
                "edited": bool(date and date.get_text(strip=True).startswith("edited")),
                "forwarded_from": fwd.get_text(" ", strip=True).replace("Forwarded from ", "") if fwd else None,
                "media": [a.get("href") for a in body.select("a.media")],
                "reactions": sum(int(c.get_text()) for c in body.select(".reaction .count")
                                 if c.get_text().strip().isdigit()),
                "text": _text(text_div),
            })
    rows.sort(key=lambda r: r["id"])
    return rows
