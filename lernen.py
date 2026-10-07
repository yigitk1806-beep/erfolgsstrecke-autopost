"""Leitet aus den Zahlen ab, welche Bauplaene funktionieren - und was daraus folgt.

Aufruf: python lernen.py  (laeuft direkt nach auswertung.py)
Liest auswertung/daten.json und auswertung/mechaniken.json, schreibt auswertung/lernen.md.

Bewertet wird nicht nach Likes, sondern nach dem, was Reichweite erzeugt:
Weiterleitungen und Speicherungen im Verhaeltnis zur erreichten Personenzahl,
dazu Profilbesuche - der Schritt, an dem bisher alles haengt.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent / "auswertung"
MINDESTENS = 2  # unter zwei Beitraegen ist es Zufall, kein Muster


def rate(beitrag: dict, feld: str) -> float | None:
    reichweite = beitrag.get("reach")
    wert = beitrag.get(feld)
    if isinstance(reichweite, (int, float)) and reichweite > 0 and isinstance(wert, (int, float)):
        return wert / reichweite * 100
    return None


def schnitt(werte: list) -> float | None:
    werte = [w for w in werte if isinstance(w, (int, float))]
    return round(sum(werte) / len(werte), 1) if werte else None


def gruppiere(beitraege: list, schluessel: str) -> dict:
    gruppen: dict[str, list] = {}
    for b in beitraege:
        if b.get(schluessel):
            gruppen.setdefault(b[schluessel], []).append(b)
    return gruppen


def tabelle(titel: str, gruppen: dict) -> list[str]:
    zeilen = ["", f"## {titel}", "",
              "| | Beiträge | Aufrufe | Reichweite | Geteilt je 100 | Gespeichert je 100 | Profil je 100 |",
              "|---|---|---|---|---|---|---|"]
    bewertet = []
    for name, gruppe in gruppen.items():
        eintrag = {
            "name": name, "anzahl": len(gruppe),
            "aufrufe": schnitt([g.get("views") for g in gruppe]),
            "reichweite": schnitt([g.get("reach") for g in gruppe]),
            "geteilt": schnitt([rate(g, "shares") for g in gruppe]),
            "gespeichert": schnitt([rate(g, "saved") for g in gruppe]),
            "profil": schnitt([rate(g, "profile_visits") for g in gruppe]),
        }
        bewertet.append(eintrag)
    bewertet.sort(key=lambda e: e["aufrufe"] or 0, reverse=True)
    for e in bewertet:
        zeilen.append("| {name} | {anzahl} | {aufrufe} | {reichweite} | {geteilt} | {gespeichert} | {profil} |".format(
            **{k: ("-" if v is None else v) for k, v in e.items()}))
    return zeilen, bewertet


def empfehlungen(mechaniken: list, formate: list, saeulen: list) -> list[str]:
    zeilen = ["", "## Was daraus folgt", ""]
    belastbar = [m for m in mechaniken if m["anzahl"] >= MINDESTENS and m["aufrufe"]]
    if len(belastbar) >= 2:
        mitte = round(median([m["aufrufe"] for m in belastbar]))
        stark = [m for m in belastbar if m["aufrufe"] > mitte * 1.25]
        schwach = [m for m in belastbar if m["aufrufe"] < mitte * 0.75]
        for m in stark:
            zeilen.append(f"- **Mehr davon:** Bauplan „{m['name']}“ liegt mit {m['aufrufe']} Aufrufen deutlich über dem Mittel "
                          f"({mitte}). Neue Varianten entwickeln, aber keine Kopie des Beitrags.")
        for m in schwach:
            zeilen.append(f"- **Weniger davon:** Bauplan „{m['name']}“ bleibt mit {m['aufrufe']} Aufrufen klar unter dem Mittel. "
                          f"Anteil zurückfahren oder den Aufbau ändern.")
    else:
        zeilen.append("- Noch zu wenig Daten pro Bauplan. Erst ab zwei Beiträgen je Bauplan wird daraus ein Muster.")

    teiler = [m for m in mechaniken if m["geteilt"]]
    if teiler:
        best = max(teiler, key=lambda m: m["geteilt"])
        zeilen.append(f"- **Weiterleitungen:** „{best['name']}“ wird am häufigsten verschickt "
                      f"({best['geteilt']} je 100 Erreichte). Weiterleiten ist das stärkste Signal für neue Leute.")
    profil = [m for m in mechaniken if m["profil"]]
    if profil:
        best = max(profil, key=lambda m: m["profil"])
        zeilen.append(f"- **Profilbesuche:** „{best['name']}“ bringt die meisten Leute aufs Profil "
                      f"({best['profil']} je 100 Erreichte). Genau dort entscheidet sich, ob jemand folgt.")
    if formate:
        bestes = max(formate, key=lambda f: f["aufrufe"] or 0)
        zeilen.append(f"- **Format:** „{bestes['name']}“ liegt vorn ({bestes['aufrufe']} Aufrufe im Schnitt).")
    if saeulen:
        beste = max(saeulen, key=lambda s: s["aufrufe"] or 0)
        zeilen.append(f"- **Thema:** „{beste['name']}“ führt aktuell ({beste['aufrufe']} Aufrufe im Schnitt).")
    return zeilen


def main() -> None:
    daten = json.loads((ROOT / "daten.json").read_text(encoding="utf-8"))
    karte = json.loads((ROOT / "mechaniken.json").read_text(encoding="utf-8")) if (ROOT / "mechaniken.json").exists() else {}
    beitraege = []
    for b in daten.get("beitraege", []):
        info = karte.get(b.get("thema") or "", {})
        b = dict(b, mechanik=info.get("mechanik"), format=info.get("format") or b.get("art"))
        beitraege.append(b)

    mech_zeilen, mechaniken = tabelle("Nach Bauplan", gruppiere(beitraege, "mechanik"))
    form_zeilen, formate = tabelle("Nach Format", gruppiere(beitraege, "format"))
    saeulen_zeilen, saeulen = tabelle("Nach Thema", gruppiere(beitraege, "saeule"))

    text = ([f"# Was funktioniert bei @{daten.get('konto')}",
             f"Stand: {datetime.now():%d.%m.%Y %H:%M} · Grundlage: {len(beitraege)} Beiträge"]
            + mech_zeilen + form_zeilen + saeulen_zeilen
            + empfehlungen(mechaniken, formate, saeulen))
    (ROOT / "lernen.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(f"lernen.md geschrieben: {len(mechaniken)} Bauplaene, {len(formate)} Formate, {len(saeulen)} Themen.")


if __name__ == "__main__":
    main()
