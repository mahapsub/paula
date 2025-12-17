"""Configuration management for Paula."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Todoist
    todoist_api_token: str = ""

    # Whisper
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_language: str = "en"

    # Ollama
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 30

    # Audio
    sample_rate: int = 16000
    max_recording_duration: int = 60

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def validate_required(self) -> None:
        """Validate that required settings are present.

        Raises:
            ValueError: If required settings are missing
        """
        if not self.todoist_api_token:
            raise ValueError(
                "TODOIST_API_TOKEN is required. "
                "Get your token from https://todoist.com/prefs/integrations"
            )


# Global settings instance
settings = Settings()
