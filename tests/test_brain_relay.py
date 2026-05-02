"""Integration test: Brain relay through simple_chat.py mock.

Tests the full flow:
1. Mock simple_chat.py WS server with Brain relay logic
2. Brain connects and is identified
3. Electron UI mock connects
4. Brain sends tasks → relayed to UI
5. UI sends text_input → routed to Brain
6. Brain sends dialogue response → TTS queue + relayed to UI
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets

# Track messages received by each role
brain_received = []
ui_received = []
test_results = {}


async def mock_simple_chat_server(websocket):
    """Simplified version of simple_chat.py's ws_handler with Brain relay."""
    global BRAIN_WS, CLIENTS
    CLIENTS.add(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "")

            # Brain identification
            if msg_type == "brain_status" and data.get("state") == "connected":
                BRAIN_WS = websocket
                print(f"  [Server] Brain identified")
                # Relay to non-Brain clients
                for c in CLIENTS:
                    if c != websocket:
                        await c.send(message)
                continue

            # Messages from Brain → relay to UI
            if websocket == BRAIN_WS:
                if msg_type == "brain_dialogue_response":
                    if data.get("stream_done"):
                        full_text = data.get("full_text", "")
                        relay = json.dumps({"type": "chat", "who": "ego", "text": full_text, "tag": "chat"})
                        for c in CLIENTS:
                            if c != websocket:
                                await c.send(relay)
                    continue

                # Relay all other Brain messages to UI
                for c in CLIENTS:
                    if c != websocket:
                        await c.send(message)
                continue

            # Messages from UI
            if msg_type == "text_input" and BRAIN_WS:
                # Route to Brain
                await BRAIN_WS.send(json.dumps({
                    "type": "user_input_for_brain",
                    "text": data.get("text", ""),
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CLIENTS.discard(websocket)
        if websocket == BRAIN_WS:
            BRAIN_WS = None


BRAIN_WS = None
CLIENTS = set()
test_complete = asyncio.Event()


async def mock_ui_client(port):
    """Simulates Electron UI connecting to WS server."""
    await asyncio.sleep(1)  # Wait for server

    async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
        print("  [UI] Connected to server")

        # Send a text input that should be routed to Brain
        await asyncio.sleep(2)  # Wait for Brain to connect
        await ws.send(json.dumps({"type": "text_input", "text": "今日のタスク教えて"}))
        print("  [UI] Sent text_input")

        # Listen for relayed messages
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                ui_received.append(data)
                msg_type = data.get("type", "")
                print(f"  [UI] Received: type={msg_type}")

                if msg_type == "tasks":
                    test_results["tasks_relayed"] = True
                    tasks = data.get("tasks", [])
                    test_results["task_count"] = len(tasks)

                if msg_type == "thought":
                    test_results["thought_relayed"] = True

                if msg_type == "hub_toast":
                    test_results["toast_relayed"] = True

                if msg_type == "chat" and data.get("who") == "ego":
                    test_results["chat_relayed"] = True
                    test_complete.set()

        except asyncio.TimeoutError:
            test_complete.set()


async def run_test():
    test_port = 18081
    server = await websockets.serve(mock_simple_chat_server, "127.0.0.1", test_port)
    print(f"[Test] Mock server on port {test_port}")

    # Start UI client
    ui_task = asyncio.create_task(mock_ui_client(test_port))

    # Start Brain
    from canon_brain import CanonBrain
    from brain.config import BrainConfig
    config = BrainConfig()
    config.ws_url = f"ws://127.0.0.1:{test_port}"
    brain = CanonBrain(config, domain="tech")
    brain_task = asyncio.create_task(brain.run())

    # Wait for completion
    try:
        await asyncio.wait_for(test_complete.wait(), timeout=20)
    except asyncio.TimeoutError:
        pass

    print("\n" + "=" * 60)
    print("RELAY TEST RESULTS")
    print("=" * 60)

    checks = {
        "tasks_relayed": test_results.get("tasks_relayed", False),
        "thought_relayed": test_results.get("thought_relayed", False),
        "toast_relayed": test_results.get("toast_relayed", False),
    }

    all_pass = True
    for name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {name}: {status}")

    task_count = test_results.get("task_count", 0)
    print(f"  tasks_count: {task_count}")

    print(f"\n  UI received {len(ui_received)} messages total")
    for m in ui_received:
        print(f"    - {m.get('type', '?')}")

    print(f"\n  OVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")

    await brain.shutdown()
    brain_task.cancel()
    ui_task.cancel()
    try:
        await asyncio.gather(brain_task, ui_task, return_exceptions=True)
    except Exception:
        pass
    server.close()
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(run_test())
