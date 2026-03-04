import json
from pathlib import Path

log_path = Path("conversation.log")
if log_path.exists():
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for i, line in enumerate(lines[-15:]):
            try:
                data = json.loads(line)
                print(f"[{i}] --- {data.get('timestamp')} ---")
                print(f"USER: {data.get('user')}")
                print(f"EGO: {data.get('assistant')}")
                m = data.get('metrics', {})
                print(f"METRICS: STT={m.get('stt_duration',0):.2f}s, LLM_FT={m.get('llm_first_token_latency',0):.2f}s")
                print("-" * 20)
            except Exception as e:
                pass
else:
    print("Log file not found.")
