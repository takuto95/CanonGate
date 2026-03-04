import sounddevice as sd
import numpy as np

devices = sd.query_devices()
hidock_ids = [i for i, d in enumerate(devices) if 'HiDock P1' in d['name'] and d['max_input_channels'] > 0]

print(f"Found HiDock IDs: {hidock_ids}")

for dev_id in hidock_ids:
    print(f"\nScanning ID {dev_id}...")
    try:
        recording = sd.rec(int(16000 * 1.0), samplerate=16000, channels=1, dtype='float32', device=dev_id)
        sd.wait()
        rms = np.sqrt(np.mean(recording**2))
        print(f"  Result RMS: {rms:.5f}")
    except Exception as e:
        print(f"  Error on ID {dev_id}: {e}")
