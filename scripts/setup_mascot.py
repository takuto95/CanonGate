import os
import zipfile
import requests
from pathlib import Path

VSEEFACE_URL = "https://github.com/emilianavt/VSeeFace/releases/download/v1.13.38c/VSeeFace-v1.13.38c.zip"
TARGET_DIR = Path(__file__).parent.parent / "VSeeFace"
ZIP_PATH = Path(__file__).parent.parent / "vseeface.zip"

def setup():
    if TARGET_DIR.exists() and (TARGET_DIR / "VSeeFace.exe").exists():
        print(f"VSeeFace is already installed at {TARGET_DIR}")
        return

    print(f"Downloading VSeeFace from {VSEEFACE_URL}...")
    try:
        response = requests.get(VSEEFACE_URL, stream=True)
        response.raise_for_status()
        with open(ZIP_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("Extracting...")
        with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
            zip_ref.extractall(TARGET_DIR.parent)
        
        # Structure check: sometimes zip contains a subfolder
        # Note: Github release zip for VSeeFace usually extracts directly to a folder named VSeeFace-v...
        extract_folder = TARGET_DIR.parent / "VSeeFace-v1.13.38c"
        if extract_folder.exists():
            if TARGET_DIR.exists():
                import shutil
                shutil.rmtree(TARGET_DIR)
            extract_folder.rename(TARGET_DIR)

        if ZIP_PATH.exists():
            ZIP_PATH.unlink()
        print("Done! VSeeFace is ready.")
    except Exception as e:
        print(f"Error during setup: {e}")
        if ZIP_PATH.exists():
            ZIP_PATH.unlink()

if __name__ == "__main__":
    setup()
