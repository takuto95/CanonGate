"""Brain configuration - loads .env and provides typed access to settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load envs in same order as simple_chat.py
load_dotenv()
_canon_dotenv = Path(__file__).resolve().parents[2] / "Canon" / ".env"
if _canon_dotenv.is_file():
    load_dotenv(_canon_dotenv)


class BrainConfig:
    """Typed access to all Brain-relevant configuration."""

    def __init__(self):
        # Paths
        self.canongate_dir = Path(__file__).resolve().parents[1]
        self.canon_dir = self.canongate_dir.parent / "Canon"
        self.agent_dir = self.canon_dir / ".agent"
        self.gtd_dir = self.agent_dir / "gtd"
        self.brain_dir = self.agent_dir / "brain"
        self.scripts_dir = self.agent_dir / "scripts"
        self.guardian_dir = self.canon_dir / "scripts" / "guardian"
        self.logs_dir = self.canongate_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # WebSocket
        self.ws_port = int(os.getenv("WS_PORT", "8080"))
        self.ws_url = f"ws://127.0.0.1:{self.ws_port}"

        # Groq (deep reasoning - primary)
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_timeout = float(os.getenv("GROQ_TIMEOUT", "10.0"))

        # Anthropic (deep reasoning - fallback when Groq is rate-limited / down)
        # Empty string disables this layer; thinker chains: Groq -> Anthropic -> Ollama
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        self.anthropic_timeout = float(os.getenv("ANTHROPIC_TIMEOUT", "30.0"))

        # Ollama (classification + last-resort fallback)
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_CLASSIFY_MODEL", "qwen3:4b")

        # Google Calendar
        self.calendar_ics_url = os.getenv("GOOGLE_CALENDAR_ICS_URL", "")
        self.calendar_poll_seconds = int(os.getenv("GOOGLE_CALENDAR_POLL_SECONDS", "60"))
        self.calendar_notify_minutes = int(os.getenv("GOOGLE_CALENDAR_NOTIFY_MINUTES_BEFORE", "30"))
        self.calendar_timezone = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Tokyo")
        self.calendar_notify_voice = os.getenv("GOOGLE_CALENDAR_NOTIFY_VOICE", "true").lower() == "true"

        # Daily Dashboard
        self.dashboard_enabled = os.getenv("DAILY_DASHBOARD_ENABLED", "true").lower() == "true"
        self.dashboard_work_start = os.getenv("DAILY_DASHBOARD_WORK_START", "09:00")
        self.dashboard_work_end = os.getenv("DAILY_DASHBOARD_WORK_END", "20:00")

        # Observer intervals (seconds)
        # 2026-05-01: cross_source を 5min→30min に緩和。executor.py dedup と組合せて
        # brain/reports/ 暴走 (1015件/日) を解消。env で上書き可。
        self.interval_report_log = 0.5
        self.interval_gtd_watch = 5
        self.interval_slack = int(os.getenv("BRAIN_INTERVAL_SLACK", "300"))            # 5 min
        self.interval_backlog = int(os.getenv("BRAIN_INTERVAL_BACKLOG", "600"))        # 10 min
        self.interval_clickup = int(os.getenv("BRAIN_INTERVAL_CLICKUP", "600"))        # 10 min
        self.interval_cross_source = int(os.getenv("BRAIN_INTERVAL_CROSS_SOURCE", "1800"))  # 30 min (was 5)
        self.interval_proactive = int(os.getenv("BRAIN_INTERVAL_PROACTIVE", "1800"))   # 30 min

        # Slack
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        self.slack_agent_thread_channel = "C0APMGTJ534"

        # Backlog
        self.backlog_api_key = os.getenv("BACKLOG_API_KEY", "")
        self.backlog_space = os.getenv("BACKLOG_SPACE", "databee")

        # ClickUp
        self.clickup_api_token = os.getenv("CLICKUP_API_TOKEN", "")
        self.clickup_team_id = os.getenv("CLICKUP_TEAM_ID", "90181932298")
