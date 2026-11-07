"""Einmalige Bestandsaufnahme aller Beitraege, um die schwaechsten zum Archivieren zu finden.

Holt Likes und Kommentare fuer jeden Beitrag des Kontos und Insights nur fuer die
KANDIDATEN mit den wenigsten Likes, damit der Zugangsschluessel nicht ins Ratenlimit laeuft.
Schreibt auswertung/alle_beitraege.json. Loescht oder aendert nichts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import publish
from auswertung import media_zahlen

ROOT = Path(__file__).resolve().parent / "auswertung"
KANDIDATEN = 60


def alle_medien() -> list[dict]:
    medien, after = [], None
    while True:
        params = {"limit": 100, "fields": "id,timestamp,media_type,caption,like_count,comments_count,permalink"}
        if after:
            params["after"] = after
        seite = publish.api("GET", "me/media", **params)
        medien += seite.get("data", [])
        after = seite.get("paging", {}).get("cursors", {}).get("after")
        if not after or not seite.get("paging", {}).get("next"):
            return medien


def insights(media_id: str) -> dict:
    try:
        daten = publish.api("GET", f"{media_id}/insights", metric="views,reach,saved,shares")
        return {e["name"]: (e.get("values") or [{}])[0].get("value") for e in daten.get("data", [])}
    except RuntimeError:
        return media_zahlen(media_id)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    beitraege = [{
        "id": m["id"],
        "zeit": m["timestamp"],
        "art": m.get("media_type"),
        "hook": (m.get("caption") or "").split("\n")[0][:70],
        "likes": m.get("like_count"),
        "kommentare": m.get("comments_count"),
        "link": m.get("permalink"),
    } for m in alle_medien()]

    for b in sorted(beitraege, key=lambda b: (b["likes"] or 0, b["kommentare"] or 0))[:KANDIDATEN]:
        b.update(insights(b["id"]))

    daten = {"stand": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "anzahl": len(beitraege), "beitraege": beitraege}
    (ROOT / "alle_beitraege.json").write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(beitraege)} Beitraege erfasst, {KANDIDATEN} mit Insights.")


if __name__ == "__main__":
    main()
