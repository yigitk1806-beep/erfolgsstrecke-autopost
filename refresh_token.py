"""Erneuert den Instagram-Zugangsschluessel, bevor er nach 60 Tagen ablaeuft."""

import os
import subprocess
import sys

import requests

token = os.environ["IG_ACCESS_TOKEN"]
resp = requests.get(
    "https://graph.instagram.com/refresh_access_token",
    params={"grant_type": "ig_refresh_token", "access_token": token},
    timeout=60,
)
data = resp.json()
if resp.status_code != 200 or "access_token" not in data:
    sys.exit(f"Erneuern fehlgeschlagen: {data.get('error', data)}")

new = data["access_token"]
print(f"::add-mask::{new}")
print(f"Schluessel erneuert, gueltig fuer {int(data.get('expires_in', 0)) // 86400} Tage.")

if new == token:
    print("Schluessel unveraendert, nichts zu speichern.")
    sys.exit(0)
if not os.environ.get("GH_TOKEN"):
    sys.exit("Neuer Schluessel erhalten, aber kein GH_PAT hinterlegt - bitte GH_PAT als Secret anlegen.")

subprocess.run(
    ["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
    input=new, text=True, check=True,
)
print("Neuer Schluessel als Secret gespeichert.")
