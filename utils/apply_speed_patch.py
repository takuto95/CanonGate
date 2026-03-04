import os
import re
from pathlib import Path

def apply_patch():
    chat_script = Path("simple_chat.py")
    if not chat_script.exists():
        print("❌ simple_chat.py not found in current directory.")
        return

    content = chat_script.read_text(encoding="utf-8")

    # 1. Update Whisper Model and Device
    content = re.sub(r'WHISPER_MODEL_SIZE = ".*?"', 'WHISPER_MODEL_SIZE = "tiny"', content)
    content = re.sub(r'WhisperModel\(WHISPER_MODEL_SIZE, device="cpu"', 'WhisperModel(WHISPER_MODEL_SIZE, device="auto"', content)

    # 2. Update VAD Silence Duration
    content = re.sub(r'VAD_SILENCE_DURATION = 0.5', 'VAD_SILENCE_DURATION = 0.35', content)

    # 3. Increase TTS Speed slightly for snappier feel
    content = re.sub(r'TTS_SPEED = "\+0%"', 'TTS_SPEED = "+10%"', content)

    chat_script.write_text(content, encoding="utf-8")
    print("✅ Performance Patch Applied to simple_chat.py!")
    print("   - Whisper: tiny (auto device)")
    print("   - VAD: 0.35s silence threshold")
    print("   - TTS Speed: +10%")

if __name__ == "__main__":
    apply_patch()
