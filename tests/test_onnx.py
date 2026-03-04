import onnxruntime as ort
import os

model_path = r"c:\Users\takut\dev\LiveTalkAiAgent\livekit-voice-adr\voices\kokoro\kokoro-v0_19_int8.onnx"
print(f"Checking {model_path}...")
print(f"File size: {os.path.getsize(model_path)}")

try:
    session = ort.InferenceSession(model_path)
    print("Successfully loaded with onnxruntime!")
except Exception as e:
    print(f"Failed to load with onnxruntime: {e}")
