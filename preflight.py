"""Prueft, ob Instagram die Testdateien in preflight/ annimmt - ohne etwas zu veroeffentlichen.

Legt nur Container an (sie verfallen nach 24 Stunden) und wartet, bis Instagram sie
verarbeitet hat. Aufruf: python preflight.py bild|reel|trial-reel
Das Ergebnis wird in preflight/ergebnis.json gesammelt.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import publish

RESULTS = Path(__file__).resolve().parent / "preflight" / "ergebnis.json"


def run(check: str) -> None:
    base = f"{publish.media_base_url()}/preflight"
    user_id = publish.account_id()
    if check == "bild":
        container = publish.create_container(user_id, image_url=f"{base}/test.jpg")
        publish.wait_until_ready(container, 180)
    elif check == "reel":
        container = publish.create_container(
            user_id, media_type="REELS", video_url=f"{base}/test.mp4", share_to_feed="true"
        )
        publish.wait_until_ready(container, 600)
    elif check == "trial-reel":
        container = publish.create_container(
            user_id, media_type="REELS", video_url=f"{base}/test.mp4",
            trial_params=json.dumps({"graduation_strategy": "SS_PERFORMANCE"}),
        )
        publish.wait_until_ready(container, 600)
    else:
        raise ValueError(f"Unbekannte Pruefung: {check}")


def main() -> None:
    check = sys.argv[1]
    results = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    try:
        run(check)
        results[check] = {"ok": True}
        print(f"{check}: angenommen")
    except Exception as exc:
        results[check] = {"ok": False, "fehler": str(exc)}
        print(f"{check}: FEHLER {exc}")
    results[check]["zeit"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if results[check]["ok"] else 1)


if __name__ == "__main__":
    main()
