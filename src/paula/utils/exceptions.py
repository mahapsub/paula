"""Custom exceptions for Paula."""


class PaulaException(Exception):
    """Base exception for Paula."""

    pass


class ConfigurationError(PaulaException):
    """Configuration/setup issues."""

    pass


class AudioError(PaulaException):
    """Audio recording/processing issues."""

    pass


class TranscriptionError(PaulaException):
    """Whisper transcription failures."""

    pass


class IntentExtractionError(PaulaException):
    """Ollama intent parsing failures."""

    pass


class TodoistError(PaulaException):
    """Todoist API issues."""

    pass
