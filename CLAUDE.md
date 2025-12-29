# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paula is a privacy-focused voice-to-todo CLI application that uses local AI models (Whisper for speech-to-text, Ollama for intent extraction) to create tasks in Todoist. All processing happens locally except the final Todoist API call.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run paula run      # Manual mode - press Enter to record/stop
uv run paula stream   # Continuous hands-free mode with VAD
uv run paula setup    # Configuration wizard
uv run paula test     # Health checks for all services

# Stream mode options
uv run paula stream --confidence 0.9   # Higher threshold
uv run paula stream --vad-level 3      # More aggressive noise filtering
uv run paula stream --dry-run          # Test without creating tasks

# Development
uv run pytest                          # Run tests
uv run ruff check src/                 # Lint
uv run black src/                      # Format
```

## Architecture

### Data Flow
Microphone → AudioRecorder/StreamingRecorder → VoiceActivityDetector (VAD) → WhisperService → OllamaService → TodoIntent → TodoistClient → Task created

### Module Structure (`src/paula/`)

- **audio/** - Audio capture and voice activity detection
  - `recorder.py` - `AudioRecorder` (manual) and `StreamingRecorder` (continuous with VAD)
  - `vad.py` - `VoiceActivityDetector` using WebRTC VAD for speech boundary detection

- **transcription/** - Speech-to-text
  - `whisper_service.py` - `WhisperService` with lazy model loading, uses faster-whisper

- **intent/** - Natural language understanding
  - `ollama_service.py` - `OllamaService` for LLM-based intent extraction, `TodoIntent` Pydantic model
  - `prompts.py` - LLM prompt templates for extracting structured task data

- **todoist/** - Task creation
  - `client.py` - `TodoistClient` with project/section caching and task creation

- **cli.py** - Click CLI with `run`, `stream`, `setup`, `test` commands
- **config.py** - Pydantic Settings for .env configuration
- **history.py** - `HistoryLogger` for JSONL logging to `.paula/history.jsonl`

### Key Data Models

`TodoIntent` (in `intent/ollama_service.py`):
- `is_task`, `confidence` - Task detection with confidence score
- `title`, `description` - Task content
- `priority` (1-4), `due_date`, `due_time`, `due_string` - Scheduling
- `project_name`, `section_name`, `labels` - Organization
- `duration`, `duration_unit`, `deadline_date` - Time tracking
- `parent_task_name`, `is_subtask` - Hierarchy

## Configuration

Settings loaded from `.env` via Pydantic Settings (`config.py`). Key settings:
- `TODOIST_API_TOKEN` - Required
- `WHISPER_MODEL` - tiny/base/small/medium/large (default: base)
- `OLLAMA_MODEL` - LLM model (default: llama3.2:3b)
- `AUTO_CREATE_CONFIDENCE` - Threshold for auto-creating tasks in stream mode (default: 0.85)
- `VAD_AGGRESSIVENESS` - 0-3, higher = more noise filtering (default: 2)

## Prerequisites

1. Ollama running locally: `ollama serve` with `ollama pull llama3.2:3b`
2. Todoist API token from https://todoist.com/prefs/integrations
3. Microphone access granted to terminal
