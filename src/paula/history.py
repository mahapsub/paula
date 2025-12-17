"""History logging for Paula transcriptions and intents."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from paula.intent.ollama_service import TodoIntent
from paula.utils.logging import get_logger

logger = get_logger(__name__)


class HistoryLogger:
    """Logs transcription history to local JSONL file.

    Each entry contains the transcription, extracted intent, and whether
    a task was created. Useful for debugging and reviewing past sessions.
    """

    def __init__(self, history_dir: Optional[Path] = None):
        """Initialize the history logger.

        Args:
            history_dir: Directory to store history file.
                        Defaults to .paula/ in current working directory.
        """
        if history_dir is None:
            history_dir = Path.cwd() / ".paula"

        self.history_dir = history_dir
        self.history_file = history_dir / "history.jsonl"

        # Ensure directory exists
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create history directory if it doesn't exist."""
        if not self.history_dir.exists():
            self.history_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created history directory: {self.history_dir}")

    def log(
        self,
        transcription: str,
        intent: TodoIntent,
        task_created: bool,
        task_id: Optional[str] = None,
        command: str = "run",
    ) -> None:
        """Log a transcription and its intent analysis.

        Args:
            transcription: The transcribed text from speech
            intent: The extracted TodoIntent from the LLM
            task_created: Whether a Todoist task was created
            task_id: The Todoist task ID if created
            command: The CLI command used ('run' or 'stream')
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "transcription": transcription,
            "intent": intent.model_dump(),
            "task_created": task_created,
            "task_id": task_id,
            "command": command,
        }

        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.debug(f"Logged history entry for: {transcription[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to write history entry: {e}")

    def get_entries(self, limit: Optional[int] = None) -> list[dict]:
        """Read history entries from file.

        Args:
            limit: Maximum number of entries to return (most recent first).
                  None returns all entries.

        Returns:
            List of history entry dictionaries
        """
        if not self.history_file.exists():
            return []

        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Failed to read history file: {e}")
            return []

        # Return most recent first
        entries.reverse()

        if limit is not None:
            entries = entries[:limit]

        return entries

    def clear(self) -> None:
        """Clear all history entries."""
        if self.history_file.exists():
            self.history_file.unlink()
            logger.info("History cleared")
