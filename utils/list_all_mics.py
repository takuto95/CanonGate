import sounddevice as sd
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        print(f"[{i}] {d['name']} (Input Channels: {d['max_input_channels']})")
