import os
import requests

def download_file(url, filename):
    print(f"Downloading {url} to {filename}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Error: {e}")

voices_dir = "livekit-voice-adr/voices/kokoro"
# Try thewh1teagle version for voices.json, it often includes more voices
download_file("https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/voices.json", os.path.join(voices_dir, "voices_onnx_community.json"))
