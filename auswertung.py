"""Holt die Zahlen der letzten Beitraege und schreibt sie nach auswertung/.

Aufruf: python auswertung.py
Erzeugt bericht.md (zum Lesen) und daten.json (zum Vergleichen spaeterer Laeufe).
Instagram benennt Kennzahlen immer wieder um - deshalb wird jede Kennzahl einzeln
abgefragt und still uebersprungen, wenn es sie nicht mehr gibt.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import publish

ROOT = Path(__file__).resolve().parent / "auswertung"
TAGE = 21
MEDIA_KENNZAHLEN = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
                    "profile_visits", "follows", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
KONTO_KENNZAHLEN = ["views", "reach", "follower_count", "profile_views"]


def media_zahlen(media_id: str) -> dict:
    """Jede Kennzahl einzeln abfragen - Instagram benennt sie staendig um."""
    werte = {}
    for kennzahl in MEDIA_KENNZAHLEN:
        daten = None
        for zusatz in ({}, {"metric_type": "total_value"}):
            try:
                daten = publish.api("GET", f"{media_id}/insights", metric=kennzahl, **zusatz)
                break
            except RuntimeError:
                continue
        if not daten:
            continue
        for eintrag in daten.get("data", []):
            if "total_value" in eintrag:
                werte[kennzahl] = eintrag["total_value"].get("value")
            for wert in eintrag.get("values", []):
                werte[kennzahl] = wert.get("value")
    return werte


def nicht_follower(user_id: str, tage: int) -> dict:
    """Reichweite aufgeteilt nach Followern und Nicht-Followern, wenn Instagram sie liefert."""
    ende = datetime.now(timezone.utc)
    start = ende - timedelta(days=tage)
    ergebnis = {}
    for kennzahl in ("reach", "views"):
        try:
            daten = publish.api("GET", f"{user_id}/insights", metric=kennzahl, period="day",
                                metric_type="total_value", breakdown="follow_type",
                                since=int(start.timestamp()), until=int(ende.timestamp()))
        except RuntimeError:
            continue
        for eintrag in daten.get("data", []):
            for teil in (eintrag.get("total_value", {}).get("breakdowns") or []):
                for ergebnis_teil in teil.get("results", []):
                    schluessel = "/".join(ergebnis_teil.get("dimension_values", []))
                    ergebnis[f"{kennzahl}:{schluessel}"] = ergebnis_teil.get("value")
    return ergebnis


def konto_zahlen(user_id: str, tage: int) -> dict:
    ende = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = ende - timedelta(days=tage)
    verlauf: dict[str, dict] = {}
    for kennzahl in KONTO_KENNZAHLEN:
        try:
            daten = publish.api("GET", f"{user_id}/insights", metric=kennzahl, period="day",
                                since=int(start.timestamp()), until=int(ende.timestamp()),
                                metric_type="total_value" if kennzahl == "views" else None)
        except RuntimeError:
            try:
                daten = publish.api("GET", f"{user_id}/insights", metric=kennzahl, period="day",
                                    since=int(start.timestamp()), until=int(ende.timestamp()))
            except RuntimeError:
                continue
        for eintrag in daten.get("data", []):
            for wert in eintrag.get("values", []):
                tag = (wert.get("end_time") or "")[:10]
                if tag:
                    verlauf.setdefault(tag, {})[kennzahl] = wert.get("value")
    return verlauf


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    konto = publish.api("GET", "me", fields="user_id,username")
    user_id = str(konto["user_id"])
    grenze = datetime.now(timezone.utc) - timedelta(days=TAGE)

    beitraege = []
    for media in publish.api("GET", "me/media", limit=40,
                             fields="id,timestamp,media_type,caption,like_count,comments_count").get("data", []):
        wann = datetime.fromisoformat(media["timestamp"].replace("+0000", "+00:00"))
        if wann < grenze:
            continue
        zeile = {
            "id": media["id"],
            "zeit": media["timestamp"],
            "art": media.get("media_type"),
            "hook": (media.get("caption") or "").split("\n")[0][:70],
            "likes": media.get("like_count"),
            "kommentare": media.get("comments_count"),
        }
        zeile.update(media_zahlen(media["id"]))
        beitraege.append(zeile)

    verlauf = konto_zahlen(user_id, TAGE)
    herkunft = nicht_follower(user_id, 7)
    daten = {"stand": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "konto": konto.get("username"), "beitraege": beitraege, "verlauf": verlauf,
             "herkunft_7_tage": herkunft}
    (ROOT / "daten.json").write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

    zeilen = [f"# Zahlen @{konto.get('username')}",
              f"Stand: {datetime.now(timezone.utc):%d.%m.%Y %H:%M} UTC · letzte {TAGE} Tage", "",
              "## Beiträge", "",
              "| Zeit | Art | Aufrufe | Reichweite | Likes | Komm. | Geteilt | Gesp. | Profil | Follows | Watchtime | Aufhänger |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in sorted(beitraege, key=lambda x: x["zeit"], reverse=True):
        wann = datetime.fromisoformat(b["zeit"].replace("+0000", "+00:00")) + timedelta(hours=2)
        art = {"VIDEO": "Reel", "CAROUSEL_ALBUM": "Karussell", "IMAGE": "Bild"}.get(b["art"], b["art"])
        watch = b.get("ig_reels_avg_watch_time")
        watch = f"{watch / 1000:.1f}s" if isinstance(watch, (int, float)) else "-"
        zeilen.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            wann.strftime("%d.%m. %H:%M"), art, b.get("views", "-"), b.get("reach", "-"),
            b.get("likes", "-"), b.get("kommentare", "-"), b.get("shares", "-"),
            b.get("saved", "-"), b.get("profile_visits", "-"), b.get("follows", "-"),
            watch, b["hook"].replace("|", "/")))

    if herkunft:
        zeilen += ["", "## Woher die Reichweite kommt (7 Tage)", "", "| Quelle | Wert |", "|---|---|"]
        for schluessel, wert in sorted(herkunft.items()):
            zeilen.append(f"| {schluessel} | {wert} |")

    if verlauf:
        zeilen += ["", "## Konto pro Tag", "", "| Tag | Aufrufe | Reichweite | Follower-Zuwachs |", "|---|---|---|---|"]
        for tag in sorted(verlauf, reverse=True):
            w = verlauf[tag]
            zeilen.append(f"| {tag} | {w.get('views', '-')} | {w.get('reach', '-')} | {w.get('follower_count', '-')} |")

    (ROOT / "bericht.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"{len(beitraege)} Beitraege ausgewertet, {len(verlauf)} Tage Verlauf.")


if __name__ == "__main__":
    main()
