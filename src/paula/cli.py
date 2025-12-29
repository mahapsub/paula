"""CLI interface for Paula voice-to-todo application."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from paula.audio.recorder import AudioRecorder, StreamingRecorder
from paula.config import settings
from paula.history import HistoryLogger
from paula.intent.ollama_service import OllamaService
from paula.todoist.client import TodoistClient
from paula.transcription.whisper_service import WhisperService
from paula.utils.exceptions import (
    AudioError,
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
        history = HistoryLogger()

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
                    # Log as not-a-task
                    history.log(transcription, intent, task_created=False, command="run")
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

            # Log to history
            history.log(transcription, intent, task_created=True, task_id=task.id, command="run")

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


def _generate_stream_display(
    status: str = "Listening...",
    is_speaking: bool = False,
    transcription: str = "",
    task_created: str = "",
    not_a_task: str = "",
    tasks_created: int = 0,
) -> Panel:
    """Generate the live display panel for stream mode.

    Args:
        status: Current status message
        is_speaking: Whether speech is being detected
        transcription: Last transcription text
        task_created: Task that was just created (if any)
        not_a_task: Message for non-task detection
        tasks_created: Total tasks created in session

    Returns:
        Rich Panel for display
    """
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="left")

    # Status indicator
    if is_speaking:
        status_text = Text("● ", style="red") + Text("Speaking...", style="bold")
    elif "Transcribing" in status:
        status_text = Text("◐ ", style="yellow") + Text(status, style="bold yellow")
    elif "Analyzing" in status:
        status_text = Text("◑ ", style="cyan") + Text(status, style="bold cyan")
    else:
        status_text = Text("○ ", style="green") + Text(status, style="bold green")

    table.add_row(status_text)
    table.add_row(Text(""))

    # Last transcription
    if transcription:
        table.add_row(Text("Last heard:", style="dim"))
        table.add_row(Text(f'"{transcription}"', style="italic"))
        table.add_row(Text(""))

    # Task created notification
    if task_created:
        table.add_row(Text(f"✅ Task created: {task_created}", style="bold green"))
        table.add_row(Text(""))

    # Not a task notification
    if not_a_task:
        table.add_row(Text(f"💭 {not_a_task}", style="dim"))
        table.add_row(Text(""))

    # Session stats
    if tasks_created > 0:
        table.add_row(Text(f"Session: {tasks_created} task(s) created", style="dim"))

    return Panel(
        table,
        title="[bold blue]Paula - Continuous Mode[/bold blue]",
        subtitle="[dim]Press Ctrl+C to stop[/dim]",
        border_style="blue",
    )


@cli.command()
@click.option(
    "--confidence",
    "-c",
    default=None,
    type=float,
    help="Min confidence for auto-create (0.0-1.0, default: 0.85)",
)
@click.option(
    "--vad-level",
    "-v",
    default=None,
    type=int,
    help="VAD aggressiveness (0-3, default: 2)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without actually creating tasks",
)
def stream(confidence: float | None, vad_level: int | None, dry_run: bool):
    """Continuous voice-to-todo mode with real-time transcription.

    Listens continuously and automatically creates tasks when detected.
    Press Ctrl+C to stop.
    """
    # Use settings defaults if not specified
    confidence_threshold = confidence if confidence is not None else settings.auto_create_confidence
    vad_aggressiveness = vad_level if vad_level is not None else settings.vad_aggressiveness

    # Validate
    if not 0.0 <= confidence_threshold <= 1.0:
        console.print("[red]Error: confidence must be between 0.0 and 1.0[/red]")
        sys.exit(1)
    if vad_aggressiveness not in range(4):
        console.print("[red]Error: vad-level must be 0, 1, 2, or 3[/red]")
        sys.exit(1)

    # Validate configuration
    try:
        settings.validate_required()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("\nRun [cyan]uv run paula setup[/cyan] to configure")
        sys.exit(1)

    # Initialize services
    try:
        recorder = StreamingRecorder(
            sample_rate=settings.sample_rate,
            vad_aggressiveness=vad_aggressiveness,
            silence_threshold_ms=settings.silence_threshold_ms,
            min_speech_ms=settings.min_speech_ms,
        )
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
        history = HistoryLogger()

        # Quick validation
        if not ollama.is_available():
            console.print("[red]Ollama is not running![/red]")
            console.print("Start it with: [cyan]ollama serve[/cyan]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Initialization failed: {e}[/red]")
        sys.exit(1)

    # Show startup info
    mode_info = "[yellow]DRY RUN[/yellow] - " if dry_run else ""
    console.print(
        f"\n{mode_info}Starting continuous mode "
        f"(confidence threshold: {confidence_threshold:.0%}, VAD level: {vad_aggressiveness})\n"
    )

    # Session stats
    tasks_created = 0
    last_transcription = ""
    last_task = ""
    last_not_task = ""

    with Live(
        _generate_stream_display(),
        refresh_per_second=4,
        console=console,
    ) as live:
        try:
            for speech_segment in recorder.start():
                # Update display: transcribing
                live.update(_generate_stream_display(
                    status="Transcribing...",
                    tasks_created=tasks_created,
                ))

                # Transcribe
                try:
                    text = whisper.transcribe_audio(speech_segment, settings.sample_rate)
                except TranscriptionError as e:
                    logger.warning(f"Transcription error: {e}")
                    live.update(_generate_stream_display(
                        status="Listening...",
                        not_a_task="Could not transcribe audio",
                        tasks_created=tasks_created,
                    ))
                    continue

                if not text:
                    live.update(_generate_stream_display(
                        status="Listening...",
                        tasks_created=tasks_created,
                    ))
                    continue

                last_transcription = text

                # Update display: analyzing
                live.update(_generate_stream_display(
                    status="Analyzing intent...",
                    transcription=last_transcription,
                    tasks_created=tasks_created,
                ))

                # Extract intent
                try:
                    intent = ollama.extract_todo(text)
                except IntentExtractionError as e:
                    logger.warning(f"Intent extraction error: {e}")
                    live.update(_generate_stream_display(
                        status="Listening...",
                        transcription=last_transcription,
                        not_a_task="Could not analyze intent",
                        tasks_created=tasks_created,
                    ))
                    continue

                # Check if it's a task with sufficient confidence
                if intent.is_task and intent.confidence >= confidence_threshold:
                    if dry_run:
                        # Dry run - just show what would be created
                        last_task = f"[DRY RUN] {intent.title}"
                        last_not_task = ""
                        live.update(_generate_stream_display(
                            status="Listening...",
                            transcription=last_transcription,
                            task_created=last_task,
                            tasks_created=tasks_created,
                        ))
                    else:
                        # Create the task
                        try:
                            task = todoist.create_task(intent)
                            tasks_created += 1
                            last_task = task.content
                            last_not_task = ""
                            # Log successful task creation
                            history.log(text, intent, task_created=True, task_id=task.id, command="stream")
                            live.update(_generate_stream_display(
                                status="Listening...",
                                transcription=last_transcription,
                                task_created=last_task,
                                tasks_created=tasks_created,
                            ))
                        except TodoistError as e:
                            logger.error(f"Failed to create task: {e}")
                            # Log failed task creation
                            history.log(text, intent, task_created=False, command="stream")
                            live.update(_generate_stream_display(
                                status="Listening...",
                                transcription=last_transcription,
                                not_a_task=f"Failed to create task: {e}",
                                tasks_created=tasks_created,
                            ))
                else:
                    # Not a task or low confidence
                    if intent.is_task:
                        last_not_task = f"Low confidence ({intent.confidence:.0%})"
                    else:
                        last_not_task = f"Not a task ({intent.confidence:.0%})"

                    last_task = ""
                    # Log as not-a-task
                    history.log(text, intent, task_created=False, command="stream")
                    live.update(_generate_stream_display(
                        status="Listening...",
                        transcription=last_transcription,
                        not_a_task=last_not_task,
                        tasks_created=tasks_created,
                    ))

        except KeyboardInterrupt:
            pass
        except AudioError as e:
            console.print(f"\n[red]Audio error: {e}[/red]")
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")
            logger.exception("Error in stream mode")
        finally:
            # Stop recorder and process any remaining audio
            remaining = recorder.stop()
            if remaining is not None and len(remaining) > 0:
                try:
                    text = whisper.transcribe_audio(remaining, settings.sample_rate)
                    if text:
                        console.print(f"\n[dim]Final segment: \"{text}\"[/dim]")
                except Exception:
                    pass

    # Summary
    console.print("\n[bold]Session complete![/bold]")
    if tasks_created > 0:
        console.print(f"[green]Created {tasks_created} task(s)[/green]")
    else:
        console.print("[dim]No tasks created[/dim]")


if __name__ == "__main__":
    cli()
