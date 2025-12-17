# Paula - Voice-to-Todo Application Implementation Plan

## Overview
Build a privacy-focused voice-to-todo app using local AI models (Whisper + Ollama) with modular Python architecture. User speaks into microphone → local transcription → local intent extraction → Todoist task creation.

## Architecture

### Module Structure (src layout - modern best practice)
```
paula/
├── pyproject.toml                   # Dependencies
├── .env.example                     # Config template
├── .gitignore                       # Exclude .env
└── src/                             # Source directory
    └── paula/                       # Main package
        ├── __init__.py
        ├── cli.py                   # CLI entry point & orchestration
        ├── config.py                # Pydantic Settings for env vars
        ├── audio/
        │   ├── __init__.py
        │   └── recorder.py          # Microphone capture with sounddevice
        ├── transcription/
        │   ├── __init__.py
        │   └── whisper_service.py   # Local Whisper integration
        ├── intent/
        │   ├── __init__.py
        │   ├── ollama_service.py    # Ollama client & TodoIntent model
        │   └── prompts.py           # LLM prompt templates
        ├── todoist/
        │   ├── __init__.py
        │   └── client.py            # Todoist API wrapper
        └── utils/
            ├── __init__.py
            ├── exceptions.py        # Custom exception hierarchy
            └── logging.py           # Rich logging setup
```

**Why src layout?**
- Clear separation between source and project files
- Prevents accidentally importing from source instead of installed package
- Forces proper installation, catching import issues early
- Modern Python best practice

### Workflow
1. User presses Enter → start recording (real-time microphone)
2. User presses Enter again → stop recording, save to temp WAV
3. Whisper transcribes locally → text output
4. Ollama extracts structured intent (title, priority, due date, etc.)
5. Todoist API creates task
6. Show confirmation, cleanup temp file, ready for next

## Key Dependencies

**Core:**
- `faster-whisper` - Local speech-to-text (faster than openai-whisper)
- `ollama` - Local LLM client (using llama3.2:3b model)
- `todoist-api-python` - Official Todoist API
- `sounddevice` + `numpy` + `scipy` - Audio recording
- `pydantic` + `python-dotenv` - Config management
- `rich` - Beautiful terminal UI with spinners/progress
- `click` - CLI framework

**Dev:**
- `pytest`, `black`, `ruff`

**pyproject.toml for src layout:**
```toml
[project.scripts]
paula = "paula.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]
```

## Configuration (.env)
```bash
TODOIST_API_TOKEN=required
WHISPER_MODEL=base
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
SAMPLE_RATE=16000
```

## Critical Implementation Details

### 1. Audio Recording (src/paula/audio/recorder.py)
- Use `sounddevice` to capture from microphone
- Record at 16kHz mono (Whisper's preferred format)
- Buffer audio chunks in memory
- Save to temporary WAV file on stop
- Show Rich spinner during recording

### 2. Whisper Transcription (src/paula/transcription/whisper_service.py)
- Use `faster-whisper` library (4x faster, lower memory)
- Lazy-load model on first use (keeps in memory after)
- Default to "base" model (74MB, good accuracy/speed tradeoff)
- Show progress bar during first-time model download
- Return plain text transcription

### 3. Intent Extraction (src/paula/intent/ollama_service.py + prompts.py)
- Define `TodoIntent` Pydantic model with fields:
  - `title: str` (required)
  - `description: Optional[str]`
  - `priority: int` (1-4, default 4)
  - `due_date: Optional[datetime]`
  - `project_name: Optional[str]`
  - `labels: list[str]`
- Send transcription to Ollama with structured prompt requesting JSON
- Parse LLM response into TodoIntent model
- Handle natural language dates ("tomorrow", "next Monday")

### 4. Todoist Integration (src/paula/todoist/client.py)
- Use `todoist-api-python` REST API wrapper
- Map TodoIntent fields to Todoist format
- Handle project lookup/creation
- Map priority (Paula 1-4 → Todoist p1-p4)
- Return task URL for confirmation

### 5. CLI & Orchestration (src/paula/cli.py)
- Click commands:
  - `paula run` - Main interactive loop
  - `paula setup` - Interactive API token setup
  - `paula test` - Health check (Whisper, Ollama, Todoist)
- Rich UI for feedback (spinners, progress bars, success/error messages)
- Error handling at each step with graceful degradation
- Cleanup temp audio files after processing

## Error Handling Strategy

**Setup Errors (block execution):**
- Missing `.env` → Guide to `paula setup`
- Invalid Todoist token → Show where to get token
- Ollama not running → Check with `ollama list`, show install guide

**Runtime Errors (degrade gracefully):**
- Mic access denied → Show system permissions guide
- Ollama timeout → Offer retry or skip intent extraction
- Todoist API failure → Show error, allow retry
- Empty recording → Prompt to try again

**Custom Exceptions:**
- `ConfigurationError`, `AudioError`, `TranscriptionError`, `IntentExtractionError`, `TodoistError`

## Implementation Steps

### Phase 1: Foundation
1. Create src layout: `src/paula/` directory structure with all module directories and `__init__.py` files
2. Update `pyproject.toml` with all dependencies and configure for src layout
3. Create `.env.example` template
4. Update `.gitignore` to exclude `.env`
5. Implement `src/paula/config.py` using Pydantic Settings
6. Implement `src/paula/utils/exceptions.py` (exception hierarchy)
7. Implement `src/paula/utils/logging.py` (Rich logging)

### Phase 2: Audio Module
8. Implement `src/paula/audio/recorder.py`:
   - `AudioRecorder` class
   - `start_recording()` / `stop_recording()` methods
   - Save to temp WAV file
9. Create basic CLI test in `src/paula/cli.py` to verify recording works

### Phase 3: Whisper Module
10. Implement `src/paula/transcription/whisper_service.py`:
    - `WhisperService` class with lazy loading
    - `transcribe(audio_path)` method
11. Add progress indicators for model download
12. Test with recorded audio

### Phase 4: Ollama Module
13. Design intent extraction prompt in `src/paula/intent/prompts.py`
14. Implement `TodoIntent` Pydantic model in `src/paula/intent/ollama_service.py`
15. Implement `OllamaService` class:
    - `extract_todo(transcription)` method
    - JSON parsing and validation
16. Test with sample transcriptions

### Phase 5: Todoist Module
17. Implement `src/paula/todoist/client.py`:
    - `TodoistClient` class
    - `create_task(todo: TodoIntent)` method
    - Project lookup/creation logic
    - Priority and date mapping
18. Test task creation in Todoist

### Phase 6: CLI & Integration
19. Build main CLI in `src/paula/cli.py`:
    - `paula run` command with interactive loop
    - `paula setup` for configuration wizard
    - `paula test` for health checks
20. Integrate all modules in workflow
21. Add Rich UI elements (spinners, progress, success messages)
22. Comprehensive error handling and recovery

### Phase 7: Documentation & Polish
23. README.md already written with usage guide
24. Test end-to-end workflow
25. Clean up temp files, optimize performance

## Prerequisites for User

**Before running Paula:**
1. Install Ollama: `brew install ollama` (macOS)
2. Start Ollama: `ollama serve`
3. Pull model: `ollama pull llama3.2:3b`
4. Get Todoist API token from https://todoist.com/prefs/integrations

## Critical Files to Create/Modify

**Create (src layout):**
- `/Users/subrat/code/paula/src/paula/__init__.py`
- `/Users/subrat/code/paula/src/paula/cli.py`
- `/Users/subrat/code/paula/src/paula/config.py`
- `/Users/subrat/code/paula/src/paula/audio/__init__.py`
- `/Users/subrat/code/paula/src/paula/audio/recorder.py`
- `/Users/subrat/code/paula/src/paula/transcription/__init__.py`
- `/Users/subrat/code/paula/src/paula/transcription/whisper_service.py`
- `/Users/subrat/code/paula/src/paula/intent/__init__.py`
- `/Users/subrat/code/paula/src/paula/intent/ollama_service.py`
- `/Users/subrat/code/paula/src/paula/intent/prompts.py`
- `/Users/subrat/code/paula/src/paula/todoist/__init__.py`
- `/Users/subrat/code/paula/src/paula/todoist/client.py`
- `/Users/subrat/code/paula/src/paula/utils/__init__.py`
- `/Users/subrat/code/paula/src/paula/utils/exceptions.py`
- `/Users/subrat/code/paula/src/paula/utils/logging.py`
- `/Users/subrat/code/paula/.env.example`
- `/Users/subrat/code/paula/.gitignore`

**Modify:**
- `/Users/subrat/code/paula/pyproject.toml` - Add dependencies and configure src layout
- `/Users/subrat/code/paula/README.md` - Already updated

**Remove:**
- `/Users/subrat/code/paula/main.py` - No longer needed (CLI moved to src/paula/cli.py)

## Performance Targets
- Transcription: <3 seconds for 10-second audio (base model)
- Intent extraction: <2 seconds (llama3.2:3b)
- Todoist API: <1 second
- Total time: <10 seconds from stop recording to task created

## Future Enhancements (Out of Scope)
- Voice Activity Detection (auto-stop)
- Multi-language support
- Offline queuing
- Task modification via voice
- Wake word activation
