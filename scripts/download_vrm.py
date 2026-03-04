"""
Download a sample VRM model to mascot-web/test.vrm for the Alter-Ego mascot UI.
Run from LiveTalkAiAgent root: python scripts/download_vrm.py
"""
import os
import sys
import requests
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
OUT_PATH = BASE_DIR / "mascot-web" / "test.vrm"

# VRM Consortium sample (VRM 1.0, works with @pixiv/three-vrm)
SAMPLE_URL = "https://raw.githubusercontent.com/vrm-c/vrm-specification/master/samples/VRM1_Constraint_Twist_Sample/vrm/VRM1_Constraint_Twist_Sample.vrm"

def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        print(f"[OK] {OUT_PATH} already exists. Delete it to re-download.")
        return 0

    print(f"Downloading VRM sample to {OUT_PATH}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(SAMPLE_URL, headers=headers, stream=True, timeout=60)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(OUT_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=262144):
                if chunk:
                    f.write(chunk)
        print(f"[OK] Saved to {OUT_PATH}")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        print("You can manually place a .vrm file as mascot-web/test.vrm")
        return 1

if __name__ == "__main__":
    sys.exit(main())
