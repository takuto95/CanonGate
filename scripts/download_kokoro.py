import os
import requests
from pathlib import Path

def download_file(url, filename):
    print(f"Downloading {url} to {filename}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        print(f"Progress: {percent:.2f}% ({downloaded / 1024 / 1024:.1f} / {total_size / 1024 / 1024:.1f} MB)    ", end='\r')
                    else:
                        print(f"Downloaded: {downloaded / 1024 / 1024:.1f} MB    ", end='\r')
        print(f"\nSuccessfully downloaded {filename}")
    except Exception as e:
        print(f"\nError downloading {url}: {e}")

SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent

# Voices URL: Download voices.bin (binary format required by kokoro-onnx)
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/v0.1.0/voices-v1.0.bin"
# Model URL: INT8 Quantized model
MODEL_URL = "https://huggingface.co/NeuML/kokoro-int8-onnx/resolve/main/model.onnx"

# Paths
VOICES_DIR = BASE_DIR / "livekit-voice-adr" / "voices" / "kokoro"
MODEL_PATH = VOICES_DIR / "kokoro-v0_19_int8.onnx"
VOICES_PATH = VOICES_DIR / "voices.bin" # Save as voices.bin

VOICES_DIR.mkdir(parents=True, exist_ok=True)

# Download voices.bin (Always download to ensure correct format)
download_file(VOICES_URL, VOICES_PATH)

# Download model (Skip if exists)
if not MODEL_PATH.exists():
    download_file(MODEL_URL, MODEL_PATH)
else:
    print(f"Model {MODEL_PATH} already exists, skipping download.")
