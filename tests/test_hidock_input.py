import sounddevice as sd
import numpy as np
import time

device_id = 1 # HiDock P1
print(f"Testing device {device_id}: マイク (HiDock P1)")

try:
    with sd.InputStream(device=device_id, channels=1, samplerate=16000) as stream:
        print("Listening for 3 seconds... Please speak into Shokz (via HiDock).")
        recording = []
        for _ in range(30): # 3 seconds
            data, overflowed = stream.read(1600)
            recording.append(data)
            rms = np.sqrt(np.mean(data**2))
            print(f"RMS: {rms:.5f}")
            time.sleep(0.1)
    
    total_recording = np.concatenate(recording)
    final_rms = np.sqrt(np.mean(total_recording**2))
    print(f"\nFinal average RMS: {final_rms:.5f}")
    if final_rms > 0.002:
        print("✅ SUCCESS: Sound detected from HiDock!")
    else:
        print("⚠️ WARNING: No significant sound detected. Check if HiDock is muted.")
except Exception as e:
    print(f"Error: {e}")
