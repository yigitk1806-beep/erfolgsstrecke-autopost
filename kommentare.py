"""Kommentare einsammeln, harmlose selbst beantworten, den Rest zur Freigabe ablegen.

Aufruf:
  python kommentare.py sammeln    - neue Kommentare holen, Einfaches beantworten
  python kommentare.py antworten  - freigegebene Antworten aus antworten.json senden

Grundsatz: Von allein beantwortet das Programm nur eindeutig harmlose Kommentare
(reine Emojis, kurze Zustimmung, eine Zahl). Alles andere - Fragen, Kritik, Links,
Beleidigungen - landet in kommentare/offen.json und wird von Hand beantwortet.
Benutzernamen werden bewusst nicht gespeichert.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_VERSION = os.environ.get("IG_API_VERSION", "v24.0")
GRAPH = f"https://graph.instagram.com/{API_VERSION}"
ROOT = Path(__file__).resolve().parent / "kommentare"
OFFEN = ROOT / "offen.json"
ANTWORTEN = ROOT / "antworten.json"
ERLEDIGT = ROOT / "erledigt.json"
VORLAGEN = ROOT / "standardantworten.json"
EINSTELLUNGEN = ROOT / "einstellungen.json"
MAX_ALTER_TAGE = 14

NUR_ZEICHEN = re.compile(r"^[^\w]+$", re.UNICODE)           # nur Emojis/Satzzeichen
NUR_ZAHL = re.compile(r"^[1-9]\s*[.!)]?$")
ZUSTIMMUNG = re.compile(
    r"^(stimmt|so ist es|so isses|wahr|leider wahr|hart aber wahr|richtig|genau|top|stark|"
    r"facts?|real|true|danke|krass|stark gesagt|gut gesagt)[\s!.,😂🔥💯👍🙏💪]*$", re.I)
NICHT_AUTOMATISCH = re.compile(
    r"(https?://|www\.|@\w|\?|\b(fake|scam|betrug|dumm|schwachsinn|bl(ö|oe)dsinn|bullshit|hurensohn|"
    r"fick|f\*ck|idiot|spinner|werbung|kooperation|zusammenarbeit|preis|kosten|kaufen)\b)", re.I)


def api(method: str, path: str, **params) -> dict:
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.request(method, f"{GRAPH}/{path}", params=params, timeout=60)
    data = resp.json()
    if resp.status_code != 200 or "error" in data:
        raise RuntimeError(f"{method} {path}: {data.get('error', data)}")
    return data


def lade(pfad: Path, standard):
    if pfad.exists():
        return json.loads(pfad.read_text(encoding="utf-8-sig"))
    return standard


def speichere(pfad: Path, inhalt) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2), encoding="utf-8")


def kategorie(text: str) -> str | None:
    """Welche Standardantwort passt - oder None, wenn ein Mensch ran muss."""
    text = text.strip()
    if not text or len(text) > 60 or NICHT_AUTOMATISCH.search(text):
        return None
    if NUR_ZAHL.match(text):
        return "zahl"
    if NUR_ZEICHEN.match(text):
        return "emoji"
    if ZUSTIMMUNG.match(text):
        return "zustimmung"
    return None


def antworte(comment_id: str, text: str) -> None:
    api("POST", f"{comment_id}/replies", message=text)


def sammeln() -> None:
    einstellungen = lade(EINSTELLUNGEN, {"auto_antworten": False})
    vorlagen = lade(VORLAGEN, {})
    erledigt = set(lade(ERLEDIGT, []))
    offen = {c["id"]: c for c in lade(OFFEN, [])}
    ich = api("GET", "me", fields="username").get("username")
    grenze = datetime.now(timezone.utc) - timedelta(days=MAX_ALTER_TAGE)

    neu_offen = 0
    beantwortet = 0
    for media in api("GET", "me/media", fields="id,timestamp,comments_count", limit=25).get("data", []):
        if not media.get("comments_count"):
            continue
        if datetime.fromisoformat(media["timestamp"].replace("+0000", "+00:00")) < grenze:
            continue
        kommentare = api("GET", f"{media['id']}/comments",
                         fields="id,text,timestamp,username,replies{username}", limit=50).get("data", [])
        for k in kommentare:
            if k["id"] in erledigt or k.get("username") == ich:
                continue
            if any(r.get("username") == ich for r in (k.get("replies", {}).get("data") or [])):
                erledigt.add(k["id"])
                continue
            art = kategorie(k.get("text", ""))
            if art and einstellungen.get("auto_antworten") and vorlagen.get(art):
                antworte(k["id"], random.choice(vorlagen[art]))
                erledigt.add(k["id"])
                offen.pop(k["id"], None)
                beantwortet += 1
                continue
            if k["id"] not in offen:
                offen[k["id"]] = {"id": k["id"], "beitrag": media["id"],
                                  "text": k.get("text", ""), "zeit": k.get("timestamp")}
                neu_offen += 1

    speichere(OFFEN, sorted(offen.values(), key=lambda c: c.get("zeit") or ""))
    speichere(ERLEDIGT, sorted(erledigt))
    print(f"Automatisch beantwortet: {beantwortet} | wartet auf Freigabe: {len(offen)} (davon neu: {neu_offen})")


def antworten() -> None:
    geplant = lade(ANTWORTEN, {})
    if not geplant:
        print("Keine freigegebenen Antworten.")
        return
    erledigt = set(lade(ERLEDIGT, []))
    offen = {c["id"]: c for c in lade(OFFEN, [])}
    fehler = 0
    for comment_id, text in list(geplant.items()):
        try:
            antworte(comment_id, text)
            erledigt.add(comment_id)
            offen.pop(comment_id, None)
            print(f"Beantwortet: {comment_id}")
        except Exception as exc:
            fehler += 1
            print(f"FEHLER bei {comment_id}: {exc}")
    speichere(ANTWORTEN, {})
    speichere(OFFEN, sorted(offen.values(), key=lambda c: c.get("zeit") or ""))
    speichere(ERLEDIGT, sorted(erledigt))
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    {"sammeln": sammeln, "antworten": antworten}[sys.argv[1]]()
