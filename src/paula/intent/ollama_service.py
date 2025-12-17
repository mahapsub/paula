"""Ollama service for intent extraction."""

import json
from datetime import datetime
from typing import Optional

import ollama
from pydantic import BaseModel, Field, field_validator

from paula.intent.prompts import format_intent_prompt
from paula.utils.exceptions import IntentExtractionError
from paula.utils.logging import get_logger

logger = get_logger(__name__)


class TodoIntent(BaseModel):
    """Structured todo intent extracted from transcription."""

    # Task Detection
    is_task: bool = Field(..., description="Does this contain an actionable task?")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")

    # Basic Info (title now optional since might not be a task)
    title: Optional[str] = Field(None, min_length=1, description="Task title")
    description: Optional[str] = Field(None, description="Task description")

    # Priority & Organization
    priority: int = Field(4, ge=1, le=4, description="Priority (1=urgent, 4=normal)")
    project_name: Optional[str] = Field(None, description="Project name")
    section_name: Optional[str] = Field(None, description="Section within project")
    labels: list[str] = Field(default_factory=list, description="Task labels")

    # Time Management (enhanced)
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_time: Optional[str] = Field(None, description="Due time in HH:MM format")
    due_string: Optional[str] = Field(None, description="Natural language for recurring tasks")
    deadline_date: Optional[str] = Field(None, description="Hard deadline date YYYY-MM-DD")

    # Duration & Effort
    duration: Optional[int] = Field(None, ge=1, description="Time estimate in specified unit")
    duration_unit: Optional[str] = Field(None, description="Unit: minute, hour, or day")

    # Hierarchy
    parent_task_name: Optional[str] = Field(None, description="Name of parent task")
    is_subtask: bool = Field(False, description="Is this a subtask?")

    # Metadata
    notes: Optional[str] = Field(None, description="Additional context or user thoughts")

    @field_validator("due_date", "deadline_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format.

        Args:
            v: Date string

        Returns:
            Validated date or None
        """
        if v is None or v == "null":
            return None

        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            logger.warning(f"Invalid date format '{v}', ignoring: {e}")
            return None

    @field_validator("due_time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format.

        Args:
            v: Time string

        Returns:
            Validated time or None
        """
        if v is None or v == "null":
            return None

        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError as e:
            logger.warning(f"Invalid time format '{v}', ignoring: {e}")
            return None

    @field_validator("duration_unit")
    @classmethod
    def validate_duration_unit(cls, v: Optional[str]) -> Optional[str]:
        """Validate duration unit.

        Args:
            v: Duration unit string

        Returns:
            Validated unit or None
        """
        if v is None or v == "null":
            return None

        valid_units = {"minute", "hour", "day"}
        if v.lower() not in valid_units:
            logger.warning(f"Invalid duration_unit '{v}', must be minute/hour/day")
            return None

        return v.lower()


class OllamaService:
    """Service for extracting todo intent using Ollama."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        timeout: int = 30,
    ):
        """Initialize the Ollama service.

        Args:
            model: Ollama model name
            base_url: Ollama server base URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._client = ollama.Client(host=base_url)

    def is_available(self) -> bool:
        """Check if Ollama service is available.

        Returns:
            True if Ollama is running and accessible
        """
        try:
            self._client.list()
            return True
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False

    def extract_todo(self, transcription: str) -> TodoIntent:
        """Extract todo intent from transcription.

        Args:
            transcription: Transcribed speech text

        Returns:
            Structured TodoIntent

        Raises:
            IntentExtractionError: If extraction fails
        """
        if not transcription or not transcription.strip():
            raise IntentExtractionError("Empty transcription provided")

        # Check if Ollama is available
        if not self.is_available():
            raise IntentExtractionError(
                "Ollama service is not available. "
                "Make sure Ollama is running with 'ollama serve'"
            )

        try:
            # Format the prompt
            prompt = format_intent_prompt(transcription)

            logger.info(f"Extracting intent using {self.model}...")
            logger.debug(f"Prompt: {prompt[:100]}...")

            # Call Ollama with JSON format
            response = self._client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                format="json",  # Force JSON output
                options={
                    "temperature": 0.1,  # Low temperature for consistent extraction
                    "num_predict": 256,  # Limit response length
                },
            )

            # Extract response text
            response_text = response["message"]["content"].strip()
            logger.debug(f"Ollama response: {response_text}")

            # Parse JSON response
            try:
                # Try to extract JSON from response (in case there's extra text)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start == -1 or json_end == 0:
                    raise ValueError("No JSON found in response")

                json_str = response_text[json_start:json_end]
                intent_data = json.loads(json_str)

            except (json.JSONDecodeError, ValueError) as e:
                raise IntentExtractionError(
                    f"Failed to parse JSON from Ollama response: {e}\n"
                    f"Response: {response_text}"
                ) from e

            # Create TodoIntent from parsed data
            try:
                todo_intent = TodoIntent(**intent_data)
                if todo_intent.is_task:
                    logger.info(f"Extracted task: {todo_intent.title} (confidence: {todo_intent.confidence:.2f})")
                else:
                    logger.info(f"Not a task (confidence: {todo_intent.confidence:.2f})")
                logger.debug(f"Full intent: {todo_intent}")
                return todo_intent

            except Exception as e:
                raise IntentExtractionError(
                    f"Failed to create TodoIntent from data: {e}\n"
                    f"Data: {intent_data}"
                ) from e

        except IntentExtractionError:
            raise
        except Exception as e:
            raise IntentExtractionError(
                f"Failed to extract intent: {e}"
            ) from e

    def check_model(self) -> bool:
        """Check if the configured model is available locally.

        Returns:
            True if model is available
        """
        try:
            response = self._client.list()
            model_names = [model.model for model in response.models]
            available = self.model in model_names

            if not available:
                logger.warning(
                    f"Model '{self.model}' not found. "
                    f"Pull it with: ollama pull {self.model}"
                )

            return available
        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
            return False
