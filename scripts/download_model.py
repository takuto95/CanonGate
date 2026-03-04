import requests
import os

def download(url, filename):
    print(f"Downloading {url} to {filename}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        print(f"Total size: {total_size / 1024 / 1024:.2f} MB")
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Error: {e}")

voices_dir = os.path.join(os.getcwd(), "livekit-voice-adr", "voices")
os.makedirs(voices_dir, exist_ok=True)

# Try Misaki from 2980
onnx_url = "https://huggingface.co/2980/piper-voices-jp/resolve/main/ja_JP-misaki-medium/ja_JP-misaki-medium.onnx"
json_url = "https://huggingface.co/2980/piper-voices-jp/resolve/main/ja_JP-misaki-medium/ja_JP-misaki-medium.onnx.json"

download(onnx_url, os.path.join(voices_dir, "ja_JP-hina-medium.onnx"))
download(json_url, os.path.join(voices_dir, "ja_JP-hina-medium.onnx.json"))
