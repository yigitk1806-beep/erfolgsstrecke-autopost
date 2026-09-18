"""Prueft die Verbindung zu Instagram, ohne etwas zu posten."""

import os
import sys

import requests

API_VERSION = os.environ.get("IG_API_VERSION", "v24.0")
GRAPH = f"https://graph.instagram.com/{API_VERSION}"
token = os.environ.get("IG_ACCESS_TOKEN")
if not token:
    sys.exit("IG_ACCESS_TOKEN fehlt.")

me = requests.get(f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token}, timeout=60).json()
if "error" in me:
    sys.exit(f"Zugangsschluessel ungueltig: {me['error'].get('message')}")
print(f"Verbunden mit @{me.get('username')} (Konto-ID {me.get('user_id')})")

expected = os.environ.get("IG_USER_ID")
if expected and expected != str(me.get("user_id")):
    sys.exit(f"IG_USER_ID passt nicht: hinterlegt {expected}, tatsaechlich {me.get('user_id')}")

limit = requests.get(
    f"{GRAPH}/{me.get('user_id')}/content_publishing_limit",
    params={"fields": "quota_usage,config", "access_token": token},
    timeout=60,
).json()
if "error" in limit:
    sys.exit(f"Veroeffentlichungs-Recht fehlt: {limit['error'].get('message')}")
data = (limit.get("data") or [{}])[0]
print(f"Veroeffentlichen erlaubt. Heute genutzt: {data.get('quota_usage', 0)} von {data.get('config', {}).get('quota_total', '?')}")
