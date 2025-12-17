"""Whisper transcription service for Paula."""

from pathlib import Path
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from paula.utils.exceptions import TranscriptionError
from paula.utils.logging import get_logger

logger = get_logger(__name__)


class WhisperService:
    """Service for transcribing audio using local Whisper model."""

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        language: str = "en",
    ):
        """Initialize the Whisper service.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on ('cpu' or 'cuda')
            language: Language code (e.g., 'en', 'es', 'fr')
        """
        self.model_name = model_name
        self.device = device
        self.language = language
        self._model: Optional[WhisperModel] = None

    def _load_model(self) -> None:
        """Lazy-load the Whisper model.

        Raises:
            TranscriptionError: If model loading fails
        """
        if self._model is not None:
            return

        try:
            logger.info(f"Loading Whisper model '{self.model_name}'...")
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type="int8" if self.device == "cpu" else "float16",
            )
            logger.info(f"Whisper model '{self.model_name}' loaded successfully")
        except Exception as e:
            raise TranscriptionError(f"Failed to load Whisper model: {e}") from e

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (WAV format)

        Returns:
            Transcribed text

        Raises:
            TranscriptionError: If transcription fails
        """
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        # Load model if not already loaded
        self._load_model()

        try:
            logger.info(f"Transcribing audio file: {audio_path}")

            # Transcribe with faster-whisper
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=5,
                vad_filter=True,  # Voice activity detection to filter silence
            )

            # Combine all segments into single text
            transcription = " ".join([segment.text.strip() for segment in segments])

            if not transcription:
                raise TranscriptionError("No speech detected in audio")

            logger.info(
                f"Transcription complete (language: {info.language}, "
                f"probability: {info.language_probability:.2f})"
            )
            logger.debug(f"Transcribed text: {transcription}")

            return transcription.strip()

        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}") from e

    def transcribe_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio directly from numpy array.

        Args:
            audio: Audio data as float32 numpy array
            sample_rate: Sample rate of the audio (default: 16000)

        Returns:
            Transcribed text

        Raises:
            TranscriptionError: If transcription fails
        """
        if audio is None or len(audio) == 0:
            raise TranscriptionError("Empty audio provided")

        # Load model if not already loaded
        self._load_model()

        try:
            duration = len(audio) / sample_rate
            logger.info(f"Transcribing audio segment: {duration:.2f}s")

            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            if audio.ndim > 1:
                audio = audio.flatten()

            # Transcribe directly from numpy array
            # faster-whisper accepts numpy arrays directly
            segments, info = self._model.transcribe(
                audio,
                language=self.language,
                beam_size=5,
                vad_filter=True,
            )

            # Combine all segments into single text
            transcription = " ".join([segment.text.strip() for segment in segments])

            if not transcription:
                logger.debug("No speech detected in audio segment")
                return ""

            logger.debug(f"Transcribed: {transcription}")
            return transcription.strip()

        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}") from e

    def is_model_loaded(self) -> bool:
        """Check if the model is loaded.

        Returns:
            True if model is loaded in memory
        """
        return self._model is not None

    def unload_model(self) -> None:
        """Unload the model from memory."""
        if self._model is not None:
            logger.debug("Unloading Whisper model from memory")
            self._model = None
