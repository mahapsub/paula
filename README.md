# Paula

A privacy-focused voice-to-todo application that uses local AI models to transcribe speech and create tasks in Todoist.

## Overview

Paula lets you create Todoist tasks by simply speaking. It uses:
- **Local Whisper** for speech-to-text transcription (no cloud API required)
- **Local Ollama** for intelligent intent extraction (understands priorities, due dates, etc.)
- **Todoist API** for creating tasks

Everything runs locally on your machine except the final Todoist API call, keeping your voice data private.

## Features

- Real-time microphone recording
- Local speech transcription with Whisper
- Intelligent intent extraction (understands "Call mom tomorrow at 2pm" and creates a task with the right title, description, and due date)
- Automatic priority detection
- Project and label support
- Beautiful terminal UI with progress indicators

## Prerequisites

Before using Paula, you need:

1. **uv** - Fast Python package installer
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Ollama** - Install and run the Ollama service:
   ```bash
   # macOS
   brew install ollama

   # Start Ollama service
   ollama serve

   # Pull the recommended model
   ollama pull llama3.2:3b
   ```

3. **Todoist API Token**
   - Get your API token from https://todoist.com/prefs/integrations
   - You'll need this during setup

## Installation

```bash
# Clone or navigate to the project
cd /Users/subrat/code/paula

# Sync dependencies with uv
uv sync

# Run the setup wizard
uv run paula setup
```

The setup wizard will guide you through configuring your Todoist API token and other settings.

## Usage

### Create tasks with your voice

```bash
uv run paula run
```

Then:
1. Press Enter to start recording
2. Speak your task (e.g., "Remind me to call mom tomorrow at 2pm")
3. Press Enter to stop recording
4. Paula will transcribe, extract intent, and create the task in Todoist

### Test your setup

```bash
uv run paula test
```

This runs health checks on Whisper, Ollama, and Todoist to ensure everything is configured correctly.

## Configuration

Paula uses a `.env` file for configuration. You can manually edit it or use `paula setup`.

Example `.env`:
```bash
TODOIST_API_TOKEN=your_token_here
WHISPER_MODEL=base
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
SAMPLE_RATE=16000
```

## How It Works

1. **Record**: Captures audio from your microphone in real-time
2. **Transcribe**: Uses local Whisper model to convert speech to text
3. **Extract Intent**: Ollama analyzes the transcription to understand:
   - Task title
   - Description
   - Priority (1-4)
   - Due date (understands natural language like "tomorrow", "next Monday")
   - Project name
   - Labels
4. **Create Task**: Adds the task to Todoist via the API
5. **Confirm**: Shows you the created task with a link

## Development

See [plans/PLAN.md](plans/PLAN.md) for the detailed implementation plan.

## Troubleshooting

### "Ollama connection failed"
- Make sure Ollama is running: `ollama serve`
- Check that the model is pulled: `ollama pull llama3.2:3b`

### "Microphone access denied"
- On macOS, go to System Settings > Privacy & Security > Microphone
- Grant permission to your terminal application

### "Invalid Todoist token"
- Get a fresh token from https://todoist.com/prefs/integrations
- Run `uv run paula setup` to reconfigure

### Slow transcription
- The first run downloads the Whisper model (may take a few minutes)
- Consider using a smaller model: set `WHISPER_MODEL=tiny` in `.env`
- Or upgrade to a larger model for better accuracy: `WHISPER_MODEL=small`

## License

MIT
