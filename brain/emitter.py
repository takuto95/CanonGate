"""Emitter - sends events from Brain to CanonGate UI via WebSocket.

Brain connects as a client to simple_chat.py's WebSocket server.
Messages use the existing protocol types where possible, adding
Brain-specific types for new functionality.
"""

import json
import logging
from datetime import datetime

log = logging.getLogger("canon-brain.emitter")


class Emitter:
    """Sends structured events through the WebSocket connection."""

    def __init__(self, websocket):
        self.ws = websocket

    async def _send(self, message: dict):
        """Send a JSON message through the WebSocket."""
        try:
            await self.ws.send(json.dumps(message))
        except Exception as e:
            log.error(f"Emitter send failed: {e}")

    # --- Existing message types (reuse) ---

    async def send_chat(self, text: str, tag: str = "brain"):
        """Display a message in the chat stream.
        tag: 'brain' for proactive insights, 'chat' for dialogue, 'soliloquy' for musings
        """
        await self._send({
            "type": "chat",
            "who": "ego",
            "text": text,
            "tag": tag,
        })

    async def send_thought(self, text: str, urgency: str = "low"):
        """Display a thought in the thought panel."""
        await self._send({
            "type": "thought",
            "text": text,
            "urgency": urgency,
            "source": "brain",
        })

    async def send_hub_alert(self, tag: str, text: str):
        """Send a priority alert to the HUD."""
        await self._send({
            "type": "hub_alert",
            "tag": tag,
            "text": text,
        })

    async def send_hub_toast(self, message: str):
        """Send a non-urgent toast notification."""
        await self._send({
            "type": "hub_toast",
            "message": message,
        })

    async def send_voice(self, text: str):
        """Request simple_chat.py to speak this text via TTS."""
        await self._send({
            "type": "log",
            "voice": True,
            "message": text,
        })

    async def send_tasks(self, tasks: list, lane_counts: dict, canon_summary: dict):
        """Broadcast updated task list."""
        await self._send({
            "type": "tasks",
            "tasks": tasks,
            "lane_counts": lane_counts,
            "canon_summary": canon_summary,
        })

    async def send_daily_timeline(self, timeline_data: dict):
        """Broadcast daily timeline update."""
        await self._send({"type": "daily_timeline", **timeline_data})

    # --- New Brain-specific message types ---

    async def send_brain_dialogue_response(self, text: str, *, stream_chunk: bool = False, stream_done: bool = False, full_text: str = ""):
        """Send dialogue response back to simple_chat.py for TTS playback.

        For streaming: send multiple messages with stream_chunk=True,
        then a final one with stream_done=True and full_text containing the complete response.
        """
        msg = {
            "type": "brain_dialogue_response",
            "text": text,
            "stream_chunk": stream_chunk,
            "stream_done": stream_done,
        }
        if stream_done:
            msg["full_text"] = full_text
        await self._send(msg)

    async def send_brain_status(self, status: dict):
        """Broadcast Brain health/status info for UI debugging."""
        await self._send({
            "type": "brain_status",
            "timestamp": datetime.now().isoformat(),
            **status,
        })

    async def send_confirm_dialog(self, message: str, action_id: str):
        """Request user confirmation for an action."""
        await self._send({
            "type": "confirm_dialog",
            "message": message,
            "action_id": action_id,
        })
