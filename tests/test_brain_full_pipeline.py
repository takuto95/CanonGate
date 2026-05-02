"""Full pipeline test: all 5 watchers + Slack + Filter."""
import asyncio, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import websockets

received = []
test_done = asyncio.Event()

async def mock_server(ws):
    try:
        async for msg in ws:
            data = json.loads(msg)
            t = data.get("type", "?")
            received.append(t)
            if t == "brain_status" and data.get("state") == "connected":
                print(f"  Brain connected (domain={data.get('domain')})")
            elif t == "tasks":
                tasks = data.get("tasks", [])
                print(f"  Tasks: {len(tasks)} items")
                test_done.set()
            elif t == "thought":
                print(f"  Thought: {data.get('text','')[:50]}")
            elif t == "hub_toast":
                print(f"  Toast: {data.get('message','')[:50]}")
    except websockets.exceptions.ConnectionClosed:
        pass

async def run():
    port = 18083
    srv = await websockets.serve(mock_server, "127.0.0.1", port)
    from canon_brain import CanonBrain
    from brain.config import BrainConfig
    config = BrainConfig()
    config.ws_url = f"ws://127.0.0.1:{port}"
    brain = CanonBrain(config, domain="tech")
    task = asyncio.create_task(brain.run())

    try:
        await asyncio.wait_for(test_done.wait(), timeout=15)
    except asyncio.TimeoutError:
        pass

    # Let watchers run briefly
    await asyncio.sleep(3)

    print(f"\n{'='*50}")
    print(f"Messages: {len(received)} total")
    types = {}
    for t in received:
        types[t] = types.get(t, 0) + 1
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")

    # Check Observer watchers
    watcher_names = [t.get_name() for t in brain.observer._tasks]
    print(f"\nActive watchers: {len(watcher_names)}")
    for w in watcher_names:
        print(f"  - {w}")

    all_expected = {"watch_report_log", "watch_gtd", "periodic_task_sync", "poll_external", "poll_slack"}
    found = set(watcher_names)
    missing = all_expected - found
    print(f"\nResult: {'ALL WATCHERS RUNNING' if not missing else f'MISSING: {missing}'}")

    await brain.shutdown()
    task.cancel()
    try: await task
    except: pass
    srv.close()
    await srv.wait_closed()

if __name__ == "__main__":
    asyncio.run(run())
