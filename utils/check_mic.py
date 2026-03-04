import sounddevice as sd

print("=== 利用可能なマイクデバイス一覧 ===")
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        print(f"  [{i}] {d['name']} (in:{d['max_input_channels']}ch, {d['default_samplerate']}Hz)")

print()
print(f"=== デフォルトデバイス ===")
try:
    default_in = sd.query_devices(kind='input')
    print(f"  デフォルト入力: {default_in['name']}")
except Exception as e:
    print(f"  エラー: {e}")

print()
print("=== RMS レベルテスト (1秒間) ===")
import numpy as np
try:
    recording = sd.rec(int(16000 * 1.0), samplerate=16000, channels=1, dtype='float32')
    sd.wait()
    rms = float(np.sqrt(np.mean(recording**2)))
    print(f"  RMS値: {rms:.5f}  (現在の閾値: 0.002)")
    if rms < 0.001:
        print("  ⚠️  非常に静か or マイクが拾えていない可能性")
    elif rms < 0.002:
        print("  ⚠️  閾値(0.002)以下。マイクが反応していない")
    else:
        print("  ✅  音声を検出できています")
except Exception as e:
    print(f"  エラー: {e}")
