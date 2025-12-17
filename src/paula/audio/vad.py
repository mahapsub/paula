"""Voice Activity Detection for real-time speech processing."""

from typing import Optional

import numpy as np
import webrtcvad

from paula.utils.logging import get_logger

logger = get_logger(__name__)


class VoiceActivityDetector:
    """Detects speech segments in audio stream using WebRTC VAD.

    Processes audio chunks and returns complete speech segments
    when silence is detected after speech.
    """

    # WebRTC VAD requires specific frame durations (10, 20, or 30 ms)
    VALID_FRAME_DURATIONS_MS = (10, 20, 30)

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
        silence_threshold_ms: int = 800,
        min_speech_ms: int = 250,
        speech_padding_ms: int = 300,
    ):
        """Initialize the VAD.

        Args:
            sample_rate: Audio sample rate (must be 8000, 16000, 32000, or 48000)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive filtering)
            silence_threshold_ms: Silence duration to trigger end of speech
            min_speech_ms: Minimum speech duration to consider valid
            speech_padding_ms: Padding to add before/after speech
        """
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError(f"Sample rate must be 8000, 16000, 32000, or 48000, got {sample_rate}")
        if aggressiveness not in range(4):
            raise ValueError(f"Aggressiveness must be 0-3, got {aggressiveness}")

        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.silence_threshold_ms = silence_threshold_ms
        self.min_speech_ms = min_speech_ms
        self.speech_padding_ms = speech_padding_ms

        # Initialize WebRTC VAD
        self._vad = webrtcvad.Vad(aggressiveness)

        # Frame size for 30ms (WebRTC VAD works with 10/20/30ms frames)
        self._frame_duration_ms = 30
        self._frame_size = int(sample_rate * self._frame_duration_ms / 1000)

        # Calculate thresholds in frames
        self._silence_frames_threshold = int(silence_threshold_ms / self._frame_duration_ms)
        self._min_speech_frames = int(min_speech_ms / self._frame_duration_ms)
        self._padding_frames = int(speech_padding_ms / self._frame_duration_ms)

        # State
        self._speech_buffer: list[np.ndarray] = []
        self._pre_speech_buffer: list[np.ndarray] = []  # Ring buffer for padding
        self._silence_frames = 0
        self._speech_frames = 0
        self._is_speaking = False
        self._chunk_buffer = np.array([], dtype=np.float32)

        logger.debug(
            f"VAD initialized: sample_rate={sample_rate}, aggressiveness={aggressiveness}, "
            f"silence_threshold={silence_threshold_ms}ms, min_speech={min_speech_ms}ms"
        )

    def _float_to_pcm16(self, audio: np.ndarray) -> bytes:
        """Convert float32 audio to 16-bit PCM bytes for WebRTC VAD.

        Args:
            audio: Float32 audio array (-1.0 to 1.0)

        Returns:
            PCM16 bytes
        """
        # Clip to valid range and convert to int16
        audio_clipped = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16)
        return audio_int16.tobytes()

    def _is_speech(self, frame: np.ndarray) -> bool:
        """Check if audio frame contains speech.

        Args:
            frame: Audio frame (float32)

        Returns:
            True if speech detected
        """
        try:
            pcm_bytes = self._float_to_pcm16(frame)
            return self._vad.is_speech(pcm_bytes, self.sample_rate)
        except Exception as e:
            logger.warning(f"VAD detection error: {e}")
            return False

    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """Process an audio chunk and return speech segment if complete.

        Args:
            audio_chunk: Audio data as float32 numpy array

        Returns:
            Complete speech segment if silence detected after speech, else None
        """
        # Flatten if needed
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.flatten()

        # Add to internal buffer
        self._chunk_buffer = np.concatenate([self._chunk_buffer, audio_chunk])

        result = None

        # Process complete frames
        while len(self._chunk_buffer) >= self._frame_size:
            frame = self._chunk_buffer[:self._frame_size]
            self._chunk_buffer = self._chunk_buffer[self._frame_size:]

            is_speech = self._is_speech(frame)

            if is_speech:
                if not self._is_speaking:
                    # Speech just started
                    self._is_speaking = True
                    self._speech_frames = 0
                    logger.debug("Speech started")

                    # Add pre-speech padding from ring buffer
                    if self._pre_speech_buffer:
                        self._speech_buffer = list(self._pre_speech_buffer)

                self._speech_buffer.append(frame)
                self._speech_frames += 1
                self._silence_frames = 0

            else:
                # Update pre-speech ring buffer (for padding)
                self._pre_speech_buffer.append(frame)
                if len(self._pre_speech_buffer) > self._padding_frames:
                    self._pre_speech_buffer.pop(0)

                if self._is_speaking:
                    # Add silence frame to buffer (post-speech padding)
                    self._speech_buffer.append(frame)
                    self._silence_frames += 1

                    if self._silence_frames >= self._silence_frames_threshold:
                        # Silence threshold reached - speech segment complete
                        if self._speech_frames >= self._min_speech_frames:
                            result = np.concatenate(self._speech_buffer)
                            logger.debug(
                                f"Speech segment complete: {len(result)/self.sample_rate:.2f}s"
                            )
                        else:
                            logger.debug(
                                f"Speech too short ({self._speech_frames} frames), discarding"
                            )

                        # Reset state
                        self._speech_buffer = []
                        self._silence_frames = 0
                        self._speech_frames = 0
                        self._is_speaking = False

        return result

    def reset(self) -> None:
        """Reset VAD state."""
        self._speech_buffer = []
        self._pre_speech_buffer = []
        self._silence_frames = 0
        self._speech_frames = 0
        self._is_speaking = False
        self._chunk_buffer = np.array([], dtype=np.float32)
        logger.debug("VAD state reset")

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently detected."""
        return self._is_speaking

    def get_buffered_speech(self) -> Optional[np.ndarray]:
        """Get any buffered speech without waiting for silence.

        Useful for cleanup when stopping recording.

        Returns:
            Buffered speech segment or None
        """
        if self._speech_buffer and self._speech_frames >= self._min_speech_frames:
            result = np.concatenate(self._speech_buffer)
            self.reset()
            return result
        return None
