"""Audio recording module for Paula."""

import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from paula.utils.exceptions import AudioError
from paula.utils.logging import get_logger

logger = get_logger(__name__)


class AudioRecorder:
    """Records audio from microphone and saves to WAV file."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """Initialize the audio recorder.

        Args:
            sample_rate: Sample rate in Hz (default: 16000 for Whisper)
            channels: Number of audio channels (1=mono, 2=stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._recording: bool = False
        self._audio_data: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None

    def start_recording(self) -> None:
        """Start recording audio from the microphone.

        Raises:
            AudioError: If recording fails to start
        """
        if self._recording:
            raise AudioError("Recording is already in progress")

        self._audio_data = []
        self._recording = True

        try:
            # Create and start the input stream
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                dtype=np.float32,
            )
            self._stream.start()
            logger.debug(
                f"Started recording: {self.sample_rate}Hz, {self.channels} channel(s)"
            )
        except Exception as e:
            self._recording = False
            raise AudioError(f"Failed to start recording: {e}") from e

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags
    ) -> None:
        """Callback function for audio stream.

        Args:
            indata: Input audio data
            frames: Number of frames
            time_info: Time information
            status: Status flags
        """
        if status:
            logger.warning(f"Audio callback status: {status}")
        if self._recording:
            self._audio_data.append(indata.copy())

    def stop_recording(self) -> Path:
        """Stop recording and save audio to a temporary WAV file.

        Returns:
            Path to the saved WAV file

        Raises:
            AudioError: If no recording is in progress or save fails
        """
        if not self._recording:
            raise AudioError("No recording in progress")

        self._recording = False

        # Stop and close the stream
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._audio_data:
            raise AudioError("No audio data recorded")

        # Concatenate all audio chunks
        audio_array = np.concatenate(self._audio_data, axis=0)

        # Create temporary WAV file
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="paula_"
        )
        temp_path = Path(temp_file.name)
        temp_file.close()

        try:
            # Save as WAV file
            wavfile.write(temp_path, self.sample_rate, audio_array)
            logger.debug(f"Saved recording to {temp_path}")
            return temp_path
        except Exception as e:
            raise AudioError(f"Failed to save audio file: {e}") from e

    def record_blocking(self, duration: Optional[float] = None) -> Path:
        """Record audio in blocking mode for a specified duration.

        Args:
            duration: Recording duration in seconds (None for manual stop)

        Returns:
            Path to the saved WAV file

        Raises:
            AudioError: If recording fails
        """
        try:
            self.start_recording()

            # Record audio
            logger.info(f"Recording for {duration}s..." if duration else "Recording...")
            recording = sd.rec(
                int((duration or 10) * self.sample_rate) if duration else int(10 * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
            )
            sd.wait()  # Wait for recording to finish

            # Store the recording
            self._audio_data = [recording]

            return self.stop_recording()

        except Exception as e:
            self._recording = False
            raise AudioError(f"Recording failed: {e}") from e

    def is_recording(self) -> bool:
        """Check if currently recording.

        Returns:
            True if recording is in progress
        """
        return self._recording

    @staticmethod
    def playback(audio_path: Path) -> None:
        """Play back an audio file.

        Args:
            audio_path: Path to WAV file to play

        Raises:
            AudioError: If playback fails
        """
        if not audio_path.exists():
            raise AudioError(f"Audio file not found: {audio_path}")

        try:
            logger.debug(f"Playing back audio: {audio_path}")
            # Read the WAV file
            sample_rate, audio_data = wavfile.read(audio_path)

            # Play the audio
            sd.play(audio_data, sample_rate)
            sd.wait()  # Wait until playback is finished
            logger.debug("Playback finished")

        except Exception as e:
            raise AudioError(f"Playback failed: {e}") from e

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices.

        Returns:
            List of device information dictionaries
        """
        try:
            devices = sd.query_devices()
            return [
                {
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                }
                for i, device in enumerate(devices)
                if device["max_input_channels"] > 0
            ]
        except Exception as e:
            logger.error(f"Failed to list audio devices: {e}")
            return []

    @staticmethod
    def check_microphone() -> bool:
        """Check if a microphone is available.

        Returns:
            True if microphone is available
        """
        try:
            devices = AudioRecorder.list_devices()
            return len(devices) > 0
        except Exception:
            return False
