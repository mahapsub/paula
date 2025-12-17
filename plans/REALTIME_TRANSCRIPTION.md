# Paula Enhancement Plan - Real-Time Transcription & Automatic Task Creation

## Overview

Transform Paula from manual record/stop/transcribe flow into a **continuous, real-time voice assistant** that:
1. Records continuously until Ctrl+C
2. Shows live transcription as user speaks
3. Automatically creates Todoist tasks when detected (confidence > 85%)

## User Requirements (Confirmed)

- **Recording**: Continuous - starts on command, runs until Ctrl+C
- **Display**: Live captions - show words as they're transcribed
- **Task Creation**: Fully automatic when confidence > 85%

## Current Architecture

### What Works Well
- `sounddevice.InputStream` already uses real-time callbacks
- Ollama intent extraction is fast (~1-2s)
- Task detection with confidence scoring already implemented
- Modular package structure

### What Must Change
| Component | Current | Required |
|-----------|---------|----------|
| Audio | Buffers all, processes on stop | Queue chunks for real-time processing |
| Transcription | File-based (complete WAV) | Chunk-based streaming |
| CLI | Sequential, blocking | Concurrent, event-driven |
| VAD | None (manual stop) | Automatic speech boundary detection |

## Technical Approach

### 1. Voice Activity Detection (VAD)
**Library**: `webrtcvad` (lightweight, battle-tested, no GPU needed)

**Why webrtcvad over alternatives**:
- `silero-vad`: More accurate but requires PyTorch (~2GB), overkill for speech boundaries
- Built-in Whisper VAD: Only works post-transcription, not real-time
- `webrtcvad`: 10KB, works at audio callback speed, good enough for speech detection

**Parameters**:
- Aggressiveness: 2 (balanced - not too sensitive, not too slow)
- Speech padding: 300ms (prevents cutting off mid-word)
- Silence threshold: 800ms (triggers transcription after pause)

### 2. Streaming Transcription
**Approach**: Sliding window with `faster-whisper` (no new dependencies)

**Why NOT whisper_streaming or WhisperLive**:
- `whisper_streaming`: Complex setup, requires specific Whisper version
- `WhisperLive`: WebSocket server architecture, over-engineered for local use
- **Simple approach**: Accumulate speech segments, transcribe complete phrases

**Strategy**:
```
Audio chunks --> VAD --> Speech buffer --> Silence detected --> Transcribe buffer
                                                                      |
                                                  Display result, extract intent
```

This is simpler than true streaming but achieves the UX goal: user speaks, sees transcription after natural pause.

**For live captions effect**: Show "Listening..." indicator while speech detected, then show transcription when ready.

### 3. Concurrency Model
**Approach**: `threading` with queues (not asyncio)

**Why threading over asyncio**:
- `sounddevice` callbacks are already threaded
- `faster-whisper` is synchronous (blocking)
- `ollama` client is synchronous
- Adding asyncio would require rewriting all services
- Threading + queues is simpler and sufficient

**Thread Architecture**:
```
Main Thread (CLI)
    |
    +--> Audio Thread (sounddevice callback)
            | [audio_queue]
            +--> VAD/Processing Thread
                    | [speech_queue]
                    +--> Transcription Thread
                            | [result_queue]
                            +--> Display/Task Creation (main thread)
```

### 4. Display Strategy
**Library**: Rich's `Live` display for updating transcription in place

**Layout**:
```
+------------------------------------------+
| Paula - Continuous Mode                  |
| Press Ctrl+C to stop                     |
+------------------------------------------+
| Status: Listening...                     |
|                                          |
| Last transcription:                      |
| "schedule dentist tomorrow at 3pm"       |
|                                          |
| Task created: Dentist (Tomorrow 3pm)     |
+------------------------------------------+
```

## Implementation Phases

### Phase 1: Add VAD Module
**New file**: `src/paula/audio/vad.py`

```python
class VoiceActivityDetector:
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.speech_buffer = []
        self.silence_frames = 0
        self.is_speaking = False

    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """Process audio chunk, return complete speech segment when silence detected."""
        is_speech = self._detect_speech(audio_chunk)

        if is_speech:
            self.speech_buffer.append(audio_chunk)
            self.silence_frames = 0
            self.is_speaking = True
        elif self.is_speaking:
            self.silence_frames += 1
            if self.silence_frames > self.silence_threshold:
                # Speech ended, return buffered audio
                result = np.concatenate(self.speech_buffer)
                self.speech_buffer = []
                self.is_speaking = False
                return result
        return None
```

**Dependency**: Add `webrtcvad>=2.0.10` to pyproject.toml

### Phase 2: Add Streaming Recorder
**Modify**: `src/paula/audio/recorder.py`

Add new class `StreamingRecorder`:

```python
class StreamingRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.vad = VoiceActivityDetector(sample_rate)
        self.speech_queue: Queue[np.ndarray] = Queue()
        self._running = False

    def start(self) -> Generator[np.ndarray, None, None]:
        """Generator that yields complete speech segments."""
        self._running = True
        self._stream = sd.InputStream(...)
        self._stream.start()

        while self._running:
            try:
                speech = self.speech_queue.get(timeout=0.1)
                yield speech
            except Empty:
                continue

    def _audio_callback(self, indata, frames, time_info, status):
        segment = self.vad.process_chunk(indata.copy())
        if segment is not None:
            self.speech_queue.put(segment)
```

### Phase 3: Add In-Memory Transcription
**Modify**: `src/paula/transcription/whisper_service.py`

Add method to transcribe from numpy array (not file):

```python
def transcribe_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
    """Transcribe audio from numpy array directly."""
    self._load_model()

    # faster-whisper can accept numpy array directly
    segments, info = self._model.transcribe(
        audio,
        language=self.language,
        beam_size=5,
        vad_filter=True,
    )

    return " ".join([seg.text.strip() for seg in segments]).strip()
```

### Phase 4: Add Continuous Mode CLI
**Modify**: `src/paula/cli.py`

Add new command `paula stream`:

```python
@cli.command()
@click.option('--confidence', default=0.85, help='Min confidence for auto-create')
def stream(confidence: float):
    """Continuous voice-to-todo mode with real-time transcription."""

    # Initialize services
    recorder = StreamingRecorder(sample_rate=settings.sample_rate)
    whisper = WhisperService(...)
    ollama = OllamaService(...)
    todoist = TodoistClient(...)

    console.print(Panel("Paula - Continuous Mode - Press Ctrl+C to stop"))

    with Live(generate_display(), refresh_per_second=4) as live:
        try:
            for speech_segment in recorder.start():
                live.update(generate_display(status="Transcribing..."))

                # Transcribe
                text = whisper.transcribe_audio(speech_segment)
                if not text:
                    continue

                live.update(generate_display(transcription=text))

                # Extract intent
                intent = ollama.extract_todo(text)

                if intent.is_task and intent.confidence >= confidence:
                    task = todoist.create_task(intent)
                    live.update(generate_display(
                        transcription=text,
                        task_created=task.content
                    ))
                else:
                    live.update(generate_display(
                        transcription=text,
                        status=f"Not a task ({intent.confidence:.0%})"
                    ))

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped[/yellow]")
```

### Phase 5: Configuration & Polish

**Modify**: `src/paula/config.py`

Add streaming settings:
```python
# Streaming mode settings
vad_aggressiveness: int = 2
silence_threshold_ms: int = 800
min_speech_ms: int = 500
auto_create_confidence: float = 0.85
```

**Update**: Help text, error handling, graceful shutdown

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/paula/audio/vad.py` | **CREATE** | Voice activity detection wrapper |
| `src/paula/audio/recorder.py` | MODIFY | Add `StreamingRecorder` class |
| `src/paula/transcription/whisper_service.py` | MODIFY | Add `transcribe_audio()` method |
| `src/paula/cli.py` | MODIFY | Add `stream` command |
| `src/paula/config.py` | MODIFY | Add VAD/streaming settings |
| `pyproject.toml` | MODIFY | Add `webrtcvad` dependency |

## New Dependency

```toml
webrtcvad = ">=2.0.10"
```

## Trade-offs & Decisions

### Why not true streaming transcription?
- **Complexity**: Requires sliding windows, partial results, word-level timestamps
- **Latency**: faster-whisper is fast enough (~500ms for short phrases)
- **Accuracy**: Complete phrases transcribe better than chunks
- **UX**: User pauses naturally between thoughts anyway

### Why keep the old `run` command?
- **Backward compatibility**: Some users prefer manual control
- **Debugging**: Easier to test individual recordings
- **Audio quality**: Can playback and verify before creating task

### Confidence threshold 85%
- **Too low (70%)**: Creates tasks from ambiguous speech
- **Too high (95%)**: Misses valid tasks with slight uncertainty
- **85%**: Good balance, can be configured via `--confidence` flag

## Example Session

```
$ uv run paula stream

+------------------------------------------+
| Paula - Continuous Mode                  |
| Press Ctrl+C to stop                     |
+------------------------------------------+

Status: Listening...

[User speaks: "buy milk tomorrow"]

Status: Transcribing...
"buy milk tomorrow"

Task created: Buy milk (Tomorrow)

Status: Listening...

[User speaks: "hmm what else do I need"]

Status: Transcribing...
"hmm what else do I need"

Not a task (72% confidence)

Status: Listening...

[User speaks: "schedule dentist next Tuesday at 3pm"]

Status: Transcribing...
"schedule dentist next Tuesday at 3pm"

Task created: Dentist appointment (Tue Dec 24, 3:00 PM)

^C
Goodbye!
```

## Risk Mitigation

1. **VAD too aggressive**: Add `--vad-level` option (0-3)
2. **Transcription errors**: Show transcription before task creation
3. **Accidental tasks**: Add `--dry-run` mode that shows what would be created
4. **Resource usage**: Whisper model stays loaded (lazy load already implemented)

## Summary

This plan adds real-time capabilities while:
- Preserving existing architecture and services
- Adding only one new dependency (`webrtcvad`)
- Keeping the simpler "phrase-at-a-time" model vs complex streaming
- Maintaining backward compatibility with manual `run` command
