"""CLI interface for Paula voice-to-todo application."""

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from paula.audio.recorder import AudioRecorder
from paula.config import settings
from paula.intent.ollama_service import OllamaService
from paula.todoist.client import TodoistClient
from paula.transcription.whisper_service import WhisperService
from paula.utils.exceptions import (
    AudioError,
    ConfigurationError,
    IntentExtractionError,
    TodoistError,
    TranscriptionError,
)
from paula.utils.logging import setup_logging, get_logger

console = Console()
logger = get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Paula - Voice-to-Todo Assistant

    Create Todoist tasks by simply speaking. Uses local AI models for privacy.
    """
    setup_logging(settings.log_level)


@cli.command()
def setup():
    """Interactive setup wizard for configuring Paula."""
    console.print(Panel.fit("Paula Setup Wizard", style="bold blue"))

    # Check if .env exists
    env_path = Path(".env")
    if env_path.exists():
        console.print("\n[yellow]Warning: .env file already exists[/yellow]")
        if not click.confirm("Do you want to overwrite it?"):
            console.print("[red]Setup cancelled[/red]")
            return

    console.print("\n[bold]Step 1: Todoist API Token[/bold]")
    console.print(
        "Get your API token from: [link]https://todoist.com/prefs/integrations[/link]"
    )
    todoist_token = click.prompt("Enter your Todoist API token", type=str)

    console.print("\n[bold]Step 2: Whisper Model[/bold]")
    console.print("Available models: tiny, base, small, medium, large")
    console.print("Recommendation: 'base' for good balance of speed and accuracy")
    whisper_model = click.prompt(
        "Whisper model", type=str, default="base", show_default=True
    )

    console.print("\n[bold]Step 3: Ollama Model[/bold]")
    console.print("Recommendation: 'llama3.2:3b' (fast and capable)")
    ollama_model = click.prompt(
        "Ollama model", type=str, default="llama3.2:3b", show_default=True
    )

    # Write .env file
    env_content = f"""# Todoist Configuration
TODOIST_API_TOKEN={todoist_token}

# Whisper Configuration
WHISPER_MODEL={whisper_model}
WHISPER_DEVICE=cpu
WHISPER_LANGUAGE=en

# Ollama Configuration
OLLAMA_MODEL={ollama_model}
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=30

# Audio Configuration
SAMPLE_RATE=16000
MAX_RECORDING_DURATION=60

# Logging
LOG_LEVEL=INFO
"""

    env_path.write_text(env_content)
    console.print(f"\n[green]✓[/green] Configuration saved to {env_path}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Make sure Ollama is running: [cyan]ollama serve[/cyan]")
    console.print(f"2. Pull the Ollama model: [cyan]ollama pull {ollama_model}[/cyan]")
    console.print("3. Run health checks: [cyan]uv run paula test[/cyan]")
    console.print("4. Start using Paula: [cyan]uv run paula run[/cyan]")


@cli.command()
def test():
    """Run health checks for all services."""
    console.print(Panel.fit("Paula Health Checks", style="bold blue"))

    all_ok = True

    # Check microphone
    console.print("\n[bold]1. Checking microphone...[/bold]")
    if AudioRecorder.check_microphone():
        console.print("[green]✓[/green] Microphone available")
        devices = AudioRecorder.list_devices()
        for device in devices[:3]:  # Show first 3 devices
            console.print(f"  - {device['name']}")
    else:
        console.print("[red]✗[/red] No microphone found")
        all_ok = False

    # Check Ollama
    console.print("\n[bold]2. Checking Ollama...[/bold]")
    try:
        ollama_service = OllamaService(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )

        if ollama_service.is_available():
            console.print("[green]✓[/green] Ollama is running")

            if ollama_service.check_model():
                console.print(f"[green]✓[/green] Model '{settings.ollama_model}' is available")
            else:
                console.print(
                    f"[red]✗[/red] Model '{settings.ollama_model}' not found. "
                    f"Pull it with: ollama pull {settings.ollama_model}"
                )
                all_ok = False
        else:
            console.print("[red]✗[/red] Ollama is not running. Start it with: ollama serve")
            all_ok = False
    except Exception as e:
        console.print(f"[red]✗[/red] Ollama check failed: {e}")
        all_ok = False

    # Check Todoist
    console.print("\n[bold]3. Checking Todoist...[/bold]")
    try:
        if not settings.todoist_api_token:
            console.print("[red]✗[/red] Todoist API token not set. Run: paula setup")
            all_ok = False
        else:
            todoist_client = TodoistClient(settings.todoist_api_token)
            todoist_client.validate_connection()
            console.print("[green]✓[/green] Todoist connection successful")
    except Exception as e:
        console.print(f"[red]✗[/red] Todoist check failed: {e}")
        all_ok = False

    # Summary
    console.print("\n" + "=" * 50)
    if all_ok:
        console.print("[bold green]All systems operational![/bold green]")
        console.print("\nRun [cyan]uv run paula run[/cyan] to start creating tasks")
    else:
        console.print("[bold red]Some checks failed[/bold red]")
        console.print("\nFix the issues above before running Paula")


@cli.command()
def run():
    """Start interactive voice-to-todo session."""
    console.print(
        Panel.fit(
            "🎤 Paula - Voice Todo Assistant\n\n"
            "Press Enter to start recording\n"
            "Press Enter again to stop\n"
            "Press Ctrl+C to exit",
            style="bold blue",
        )
    )

    # Validate configuration
    try:
        settings.validate_required()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("\nRun [cyan]uv run paula setup[/cyan] to configure")
        sys.exit(1)

    # Initialize services
    try:
        recorder = AudioRecorder(sample_rate=settings.sample_rate)
        whisper = WhisperService(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            language=settings.whisper_language,
        )
        ollama = OllamaService(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )
        todoist = TodoistClient(settings.todoist_api_token)

        # Quick validation
        if not ollama.is_available():
            console.print("[red]Ollama is not running![/red]")
            console.print("Start it with: [cyan]ollama serve[/cyan]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Initialization failed: {e}[/red]")
        sys.exit(1)

    # Main loop
    while True:
        try:
            console.print("\n[dim]Ready for next task...[/dim]")
            input("Press Enter to start recording...")

            # Start recording
            recorder.start_recording()
            console.print("[red]●[/red] Recording... (press Enter to stop)")
            input()  # Wait for user to press Enter again

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Stop recording and save
                task_id = progress.add_task("Saving recording...", total=None)
                audio_path = recorder.stop_recording()
                progress.update(task_id, description="[green]✓[/green] Recording saved")

                # Play back the recording
                progress.update(task_id, description="🔊 Playing back recording...")
                AudioRecorder.playback(audio_path)
                progress.update(task_id, description="[green]✓[/green] Playback complete")

                # Transcribe
                progress.update(task_id, description="Transcribing...")
                transcription = whisper.transcribe(audio_path)
                progress.update(task_id, description=f"[green]✓[/green] Transcribed")
                console.print(f'[italic]"{transcription}"[/italic]')

                # Extract intent
                progress.update(task_id, description="Analyzing intent...")
                intent = ollama.extract_todo(transcription)
                progress.update(task_id, description="[green]✓[/green] Analysis complete")

            # Check if this is actually a task
            if not intent.is_task:
                console.print(f"\n[yellow]ℹ️  Not a task detected[/yellow] (confidence: {intent.confidence:.0%})")
                if intent.notes:
                    console.print(f"[dim]{intent.notes}[/dim]")
                console.print(f'\n[italic]You said: "{transcription}"[/italic]')

                # Option to create anyway
                if click.confirm("\nDo you want to create a task anyway?", default=False):
                    # Prompt for task title
                    title = click.prompt("Enter task title", type=str)
                    intent.title = title
                    intent.is_task = True
                else:
                    continue

            # Show extracted intent with ALL fields
            console.print(f"\n[bold cyan]📋 Detected Task[/bold cyan] (confidence: {intent.confidence:.0%})")
            console.print(f"[bold]Title:[/bold] {intent.title}")

            if intent.description:
                console.print(f"[bold]Description:[/bold] {intent.description}")

            # Priority
            priority_labels = {1: "🔴 Urgent", 2: "🟠 High", 3: "🟡 Medium", 4: "⚪ Normal"}
            console.print(f"[bold]Priority:[/bold] {priority_labels.get(intent.priority, 'Normal')}")

            # Time info
            if intent.due_date:
                due_display = intent.due_date
                if intent.due_time:
                    due_display += f" at {intent.due_time}"
                console.print(f"[bold]Due:[/bold] 📅 {due_display}")

            if intent.due_string:
                console.print(f"[bold]Recurring:[/bold] 🔁 {intent.due_string}")

            if intent.deadline_date:
                console.print(f"[bold]Deadline:[/bold] ⚠️  {intent.deadline_date}")

            # Duration
            if intent.duration and intent.duration_unit:
                console.print(f"[bold]Duration:[/bold] ⏱️  {intent.duration} {intent.duration_unit}(s)")

            # Organization
            if intent.project_name:
                console.print(f"[bold]Project:[/bold] 📁 {intent.project_name}")

            if intent.section_name:
                console.print(f"[bold]Section:[/bold] 📂 {intent.section_name}")

            if intent.labels:
                console.print(f"[bold]Labels:[/bold] 🏷️  {', '.join(intent.labels)}")

            # Hierarchy
            if intent.parent_task_name:
                console.print(f"[bold]Parent Task:[/bold] ⬆️  {intent.parent_task_name}")

            if intent.is_subtask:
                console.print("[bold]Type:[/bold] 📎 Subtask")

            # Create task
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task_id = progress.add_task("Creating Todoist task...", total=None)
                task = todoist.create_task(intent)
                progress.update(task_id, description="[green]✓[/green] Task created!")

            # Show success
            console.print(
                f"\n[bold green]✅ Task created:[/bold green] {task.content}"
            )
            task_url = todoist.get_task_url(task)
            console.print(f"[link]{task_url}[/link]")

            # Clean up temp audio file
            if audio_path.exists():
                audio_path.unlink()

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Goodbye![/yellow]")
            break
        except AudioError as e:
            console.print(f"\n[red]Audio error: {e}[/red]")
        except TranscriptionError as e:
            console.print(f"\n[red]Transcription error: {e}[/red]")
        except IntentExtractionError as e:
            console.print(f"\n[red]Intent extraction error: {e}[/red]")
        except TodoistError as e:
            console.print(f"\n[red]Todoist error: {e}[/red]")
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")
            logger.exception("Unexpected error in main loop")


if __name__ == "__main__":
    cli()
