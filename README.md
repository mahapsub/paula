# Paula

A privacy-focused voice-to-todo CLI that uses local AI (Whisper + Ollama) to create Todoist tasks from speech.

## Features

- **Two modes**: Manual (`run`) or hands-free continuous (`stream`) with voice activity detection
- **100% local processing**: Speech and intent extraction run on your machine
- **Smart scheduling**: Recurring ("every Monday"), specific times ("Tuesday at 3pm"), or date-only ("by Friday")
- **Rich task metadata**: Projects, sections, labels, priorities, durations, subtasks
- **Confidence-based auto-creation**: Only creates tasks when AI is sufficiently confident
- **History logging**: JSONL log of all transcriptions and intents

## Quick Start

```bash
# Install dependencies
uv sync

# Setup (API token, models)
uv run paula setup

# Verify everything works
uv run paula test

# Manual mode (press Enter to record/stop)
uv run paula run

# Continuous hands-free mode
uv run paula stream
```

## Prerequisites

1. **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Ollama**: `brew install ollama && ollama serve && ollama pull llama3.2:3b`
3. **Todoist API token**: Get from https://todoist.com/prefs/integrations

## Architecture

```
Microphone → VAD → Whisper → Ollama → Todoist API
                                   ↓
                            .paula/history.jsonl
```

**Data Flow:**
1. Audio captured via sounddevice
2. Voice Activity Detector (WebRTC VAD) finds speech boundaries
3. Whisper (faster-whisper) transcribes locally
4. Ollama (local LLM) extracts structured intent
5. TodoistClient creates task with full metadata

**Key Modules** (`src/paula/`):
- `audio/` - Recording (`AudioRecorder`, `StreamingRecorder`) and VAD
- `transcription/` - `WhisperService` with lazy model loading
- `intent/` - `OllamaService` extracting `TodoIntent` Pydantic model
- `todoist/` - `TodoistClient` with project/section caching
- `cli.py` - Click commands (run, stream, setup, test)

## Commands

### Manual Mode
```bash
uv run paula run
```
Press Enter to record, speak, press Enter to stop. Task created if detected.

### Stream Mode (Hands-Free)
```bash
# Default (auto-creates at 85% confidence)
uv run paula stream

# Higher confidence threshold
uv run paula stream --confidence 0.9

# More aggressive noise filtering
uv run paula stream --vad-level 3

# Test without creating tasks
uv run paula stream --dry-run
```

### Configuration
```bash
uv run paula setup    # Interactive wizard
uv run paula test     # Health checks
```

## Scheduling Examples

**Recurring:** "remind me to take vitamins every morning"
**Specific time:** "dentist appointment Tuesday at 3pm"
**Date only:** "finish report by Friday"
**With duration:** "meeting for 2 hours"

Paula uses your system timezone for tasks with specific times.

## Configuration

Settings in `.env` (created by `paula setup`):

```bash
# Required
TODOIST_API_TOKEN=your_token_here

# Models
WHISPER_MODEL=base              # tiny/base/small/medium/large
OLLAMA_MODEL=llama3.2:3b

# Stream mode
AUTO_CREATE_CONFIDENCE=0.85     # Threshold for auto-creating tasks
VAD_AGGRESSIVENESS=2            # 0-3, higher = more noise filtering

# Optional
WHISPER_DEVICE=cpu              # cpu or cuda
OLLAMA_BASE_URL=http://localhost:11434
LOG_LEVEL=INFO
```

## TodoIntent Data Model

Extracted by Ollama from transcription:

```python
is_task: bool              # Task detected?
confidence: float          # 0.0-1.0 confidence score
title: str                 # Task title
description: str           # Additional details
priority: int              # 1 (urgent) to 4 (normal)
project_name: str          # Target project
section_name: str          # Section within project
labels: list[str]          # Task labels
due_date: str              # YYYY-MM-DD
due_time: str              # HH:MM (combined with due_date)
due_string: str            # Natural language ("every Monday")
duration: int              # Time estimate value
duration_unit: str         # minute/hour/day
parent_task_name: str      # For subtasks
is_subtask: bool           # Subtask flag
```

## History File

All sessions logged to `.paula/history.jsonl`:

```json
{
  "timestamp": "2025-12-17T14:30:45.123456",
  "transcription": "buy milk tomorrow",
  "intent": {
    "is_task": true,
    "confidence": 0.95,
    "title": "Buy milk",
    "due_date": "2025-12-18"
  },
  "task_created": true,
  "task_id": "8675309"
}
```

Useful for debugging, reviewing transcriptions, and analyzing patterns.

## Troubleshooting

**Ollama connection failed**: `ollama serve` and `ollama pull llama3.2:3b`
**Microphone access denied**: Grant permission in System Settings (macOS)
**Invalid Todoist token**: Get fresh token from https://todoist.com/prefs/integrations
**Slow transcription**: First run downloads model; use `WHISPER_MODEL=tiny` for speed
**VAD issues**: Adjust `--vad-level 1` (less sensitive) or `3` (more aggressive)
**Tasks not auto-creating**: Lower threshold with `--confidence 0.7` or check `.paula/history.jsonl`

## Future Improvements

### Critical Fixes (from PR review)
1. **Dynamic date in prompts** - Currently hardcoded to 2025-12-16; needs `datetime.now()` injection
2. **Unit tests** - Missing tests for `_build_due_params()`, duration conversion, timezone handling
3. **Timezone configuration** - Allow user to override system timezone (Docker/CI environments)

### Enhanced Scheduling
4. **DST-aware timezone handling** - Use `zoneinfo.ZoneInfo` instead of naive datetime + `replace()`
5. **Duration validation** - Cap extreme values (e.g., 1000 hours → warn/limit)
6. **Recurring + time support** - Handle "every Monday at 3pm" without losing time component

### User Experience
7. **Visible time parse failures** - Notify user when time component is dropped due to parse errors
8. **Task editing** - Voice commands to modify existing tasks
9. **Multi-language support** - Extend beyond English transcription
10. **Web UI** - Optional browser interface for history review and settings

### Infrastructure
11. **Integration tests** - Mock Todoist API for end-to-end testing
12. **CI/CD pipeline** - Automated testing, linting, and releases
13. **Rate limiting** - Protect against Todoist API limits in stream mode
14. **Model caching** - Pre-download models during install to avoid first-run delay

### Advanced Features
15. **Context awareness** - Remember recent tasks for smarter intent extraction
16. **Task templates** - Pre-configured task structures for common patterns
17. **Voice feedback** - TTS confirmation of created tasks
18. **Batch operations** - "Add three tasks: X, Y, and Z"

## Project Structure

```
paula/
├── src/paula/
│   ├── cli.py              # Commands: run, stream, setup, test
│   ├── config.py           # Pydantic Settings from .env
│   ├── history.py          # JSONL logging
│   ├── audio/              # AudioRecorder, StreamingRecorder, VAD
│   ├── transcription/      # WhisperService
│   ├── intent/             # OllamaService, TodoIntent, prompts
│   └── todoist/            # TodoistClient
├── .env                    # Configuration (git ignored)
├── .paula/                 # History (git ignored)
└── pyproject.toml
```

## License

MIT
