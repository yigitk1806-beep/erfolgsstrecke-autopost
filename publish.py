"""Veroeffentlicht freigegebene Beitraege aus queue/ auf Instagram.

Laeuft per GitHub Actions alle 15 Minuten. Ein Beitrag wird nur
veroeffentlicht, wenn in seiner post.json "approved": true steht und
der Zeitpunkt "publish_at" erreicht ist.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import requests

API_VERSION = os.environ.get("IG_API_VERSION", "v24.0")
GRAPH = f"https://graph.instagram.com/{API_VERSION}"
ROOT = Path(__file__).resolve().parent
QUEUE = Path(os.environ.get("QUEUE_DIR", ROOT / "queue"))
PUBLISHED = Path(os.environ.get("PUBLISHED_DIR", ROOT / "published"))
MAX_PER_RUN = 3
MAX_ATTEMPTS = 3
MAX_HASHTAGS = 5  # seit 12/2025 empfiehlt Instagram Beitraege mit mehr Hashtags nicht weiter


def media_base_url() -> str:
    base = os.environ.get("MEDIA_BASE_URL")
    if base:
        return base.rstrip("/")
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}"


def api(method: str, path: str, **params) -> dict:
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.request(method, f"{GRAPH}/{path}", params=params, timeout=60)
    data = resp.json()
    if resp.status_code != 200 or "error" in data:
        raise RuntimeError(f"{method} {path}: {data.get('error', data)}")
    return data


@lru_cache(maxsize=None)
def account_id() -> str:
    """IG_USER_ID, falls gesetzt - sonst die Konto-ID, zu der der Zugangsschluessel gehoert."""
    return os.environ.get("IG_USER_ID") or str(api("GET", "me", fields="user_id")["user_id"])


def wait_until_ready(container_id: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    while True:
        info = api("GET", container_id, fields="status_code,status")
        status = info.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {container_id}: {status} - {info.get('status', '')}")
        if time.time() > deadline:
            raise RuntimeError(f"Container {container_id} nach {timeout_s}s noch {status}")
        time.sleep(20)


def create_container(user_id: str, **fields) -> str:
    return api("POST", f"{user_id}/media", **fields)["id"]


def publish_post(folder: Path, post: dict, dry_run: bool) -> str:
    base = f"{media_base_url()}/queue/{quote(folder.name)}"
    urls = [f"{base}/{quote(name)}" for name in post["media"]]
    kind = post["type"]
    caption = post["caption"]

    if kind == "carousel" and not 2 <= len(urls) <= 10:
        raise ValueError("Karussell braucht 2 bis 10 Bilder")
    if kind in ("image", "carousel") and not all(u.lower().endswith((".jpg", ".jpeg")) for u in urls):
        raise ValueError("Instagram akzeptiert nur JPEG-Bilder")
    if len(re.findall(r"#\w+", caption)) > MAX_HASHTAGS:
        raise ValueError(f"Mehr als {MAX_HASHTAGS} Hashtags - Instagram wuerde den Beitrag nicht empfehlen")

    if dry_run:
        print(f"  [Probelauf] {kind}, {len(urls)} Datei(en):")
        for url in urls:
            print(f"    {url}")
        return "dry-run"

    user_id = account_id()
    if kind == "image":
        container = create_container(user_id, image_url=urls[0], caption=caption)
        wait_until_ready(container, 120)
    elif kind == "carousel":
        children = []
        for url in urls:
            child = create_container(user_id, image_url=url, is_carousel_item="true")
            wait_until_ready(child, 120)
            children.append(child)
        container = create_container(
            user_id, media_type="CAROUSEL", children=",".join(children), caption=caption
        )
        wait_until_ready(container, 120)
    elif kind == "reel":
        fields = {"media_type": "REELS", "video_url": urls[0], "caption": caption}
        if post.get("trial"):
            # Trial Reel: erst nur Nicht-Followern zeigen, SS_PERFORMANCE schaltet bei Erfolg frei
            fields["trial_params"] = json.dumps({"graduation_strategy": post["trial"]})
        else:
            fields["share_to_feed"] = "true"
        container = create_container(user_id, **fields)
        wait_until_ready(container, 600)
    else:
        raise ValueError(f"Unbekannter Beitragstyp: {kind}")

    return api("POST", f"{user_id}/media_publish", creation_id=container)["id"]


def load_due_posts(now: datetime) -> list:
    due = []
    if not QUEUE.exists():
        return due
    for folder in sorted(p for p in QUEUE.iterdir() if p.is_dir()):
        meta = folder / "post.json"
        if not meta.exists():
            continue
        try:
            post = json.loads(meta.read_text(encoding="utf-8-sig"))
            when = datetime.fromisoformat(post["publish_at"].replace("Z", "+00:00"))
        except (ValueError, KeyError) as exc:
            print(f"- {folder.name}: post.json fehlerhaft ({exc}), uebersprungen")
            continue
        if not post.get("approved"):
            print(f"- {folder.name}: nicht freigegeben, uebersprungen")
            continue
        if post.get("attempts", 0) >= MAX_ATTEMPTS:
            print(f"- {folder.name}: {MAX_ATTEMPTS} Fehlversuche, wartet auf Pruefung")
            continue
        if when <= now:
            due.append((folder, post))
    return due


def save(folder: Path, post: dict) -> None:
    (folder / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="nur pruefen, nichts posten")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    due = load_due_posts(now)
    if not due:
        print("Nichts faellig.")
    failures = 0
    for folder, post in due[:MAX_PER_RUN]:
        print(f"> {folder.name} ({post['type']}, geplant {post['publish_at']})")
        try:
            media_id = publish_post(folder, post, args.dry_run)
        except Exception as exc:
            failures += 1
            print(f"  FEHLER: {exc}")
            if not args.dry_run:
                post["attempts"] = post.get("attempts", 0) + 1
                post["last_error"] = f"{datetime.now(timezone.utc).isoformat()} {exc}"
                save(folder, post)
            continue
        if args.dry_run:
            continue
        post["published_id"] = media_id
        post["published_at"] = datetime.now(timezone.utc).isoformat()
        post.pop("last_error", None)
        save(folder, post)
        PUBLISHED.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(PUBLISHED / folder.name))
        print(f"  veroeffentlicht: {media_id}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
