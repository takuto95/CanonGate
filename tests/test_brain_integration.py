"""Integration test: Canon Brain connects to a mock WS server.

Verifies the full pipeline: Brain connects -> Observer runs -> tasks broadcast.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets

# Collect messages received by the mock server
received_messages = []
test_complete = asyncio.Event()


async def mock_ws_handler(websocket):
    """Mock simple_chat.py WS server. Collects all messages from Brain."""
    print("[MockWS] Brain client connected")
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            received_messages.append(data)

            if msg_type == "brain_status" and data.get("state") == "connected":
                print(f"[MockWS] Brain announced: state={data['state']}, domain={data.get('domain')}")

            elif msg_type == "hub_toast":
                print(f"[MockWS] Toast: {data.get('message')}")

            elif msg_type == "thought":
                print(f"[MockWS] Thought: {data.get('text', '')[:80]}")

            elif msg_type == "tasks":
                tasks = data.get("tasks", [])
                lc = data.get("lane_counts", {})
                print(f"[MockWS] Tasks broadcast: {len(tasks)} tasks, your_turn={lc.get('your_turn', 0)}")
                # After receiving tasks, test is successful
                test_complete.set()

            elif msg_type == "log" and data.get("voice"):
                print(f"[MockWS] Voice request: {data.get('message', '')[:60]}")

            else:
                print(f"[MockWS] Message: type={msg_type}")

    except websockets.exceptions.ConnectionClosed:
        print("[MockWS] Brain disconnected")


async def run_test():
    # Start mock WS server on a test port
    test_port = 18080
    server = await websockets.serve(mock_ws_handler, "127.0.0.1", test_port)
    print(f"[Test] Mock WS server started on port {test_port}")

    # Start Brain connecting to mock server
    from canon_brain import CanonBrain
    from brain.config import BrainConfig

    config = BrainConfig()
    config.ws_url = f"ws://127.0.0.1:{test_port}"

    brain = CanonBrain(config, domain="tech")
    brain_task = asyncio.create_task(brain.run())

    # Wait for test completion or timeout
    try:
        await asyncio.wait_for(test_complete.wait(), timeout=15)
        print("\n" + "=" * 60)
        print("TEST RESULT: PASS")
        print("=" * 60)

        # Summary
        msg_types = {}
        for m in received_messages:
            t = m.get("type", "unknown")
            msg_types[t] = msg_types.get(t, 0) + 1

        print(f"\nMessages received ({len(received_messages)} total):")
        for t, count in sorted(msg_types.items()):
            print(f"  {t}: {count}")

        # Verify key messages
        has_status = any(m.get("type") == "brain_status" for m in received_messages)
        has_toast = any(m.get("type") == "hub_toast" for m in received_messages)
        has_tasks = any(m.get("type") == "tasks" for m in received_messages)
        has_thought = any(m.get("type") == "thought" for m in received_messages)

        print(f"\nKey checks:")
        print(f"  brain_status received: {'OK' if has_status else 'MISSING'}")
        print(f"  hub_toast received: {'OK' if has_toast else 'MISSING'}")
        print(f"  tasks broadcast: {'OK' if has_tasks else 'MISSING'}")
        print(f"  thought emitted: {'OK' if has_thought else 'MISSING'}")

        # Show task details
        for m in received_messages:
            if m.get("type") == "tasks":
                tasks = m.get("tasks", [])
                your_turn = [t for t in tasks if t.get("lane") == "your_turn"]
                print(f"\n  Task details: {len(tasks)} total, {len(your_turn)} your_turn")
                for t in your_turn[:3]:
                    print(f"    - {t.get('title', '?')[:50]} [{t.get('priority_label', '')}]")
                if len(your_turn) > 3:
                    print(f"    ... and {len(your_turn) - 3} more")
                break

    except asyncio.TimeoutError:
        print("\n" + "=" * 60)
        print("TEST RESULT: TIMEOUT (15s)")
        print("=" * 60)
        print(f"Messages received so far: {len(received_messages)}")
        for m in received_messages:
            print(f"  {m.get('type', '?')}: {str(m)[:100]}")

    finally:
        await brain.shutdown()
        brain_task.cancel()
        try:
            await brain_task
        except (asyncio.CancelledError, Exception):
            pass
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(run_test())
