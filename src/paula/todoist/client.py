"""Todoist API client for Paula."""

from datetime import datetime, timezone
from typing import Optional

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task

from paula.intent.ollama_service import TodoIntent
from paula.utils.exceptions import TodoistError
from paula.utils.logging import get_logger

logger = get_logger(__name__)


class TodoistClient:
    """Client for interacting with Todoist API."""

    # Priority mapping: Paula (1-4) -> Todoist (p1-p4)
    PRIORITY_MAP = {
        1: 4,  # Urgent -> p1 (highest in Todoist)
        2: 3,  # High -> p2
        3: 2,  # Medium -> p3
        4: 1,  # Normal -> p4 (lowest in Todoist)
    }

    def __init__(self, api_token: str):
        """Initialize Todoist client.

        Args:
            api_token: Todoist API token

        Raises:
            TodoistError: If token is invalid
        """
        if not api_token:
            raise TodoistError("Todoist API token is required")

        try:
            self._api = TodoistAPI(api_token)
            self._projects_cache: Optional[dict[str, str]] = None
            self._sections_cache: dict[str, dict[str, str]] = {}  # project_id -> {section_name -> section_id}
        except Exception as e:
            raise TodoistError(f"Failed to initialize Todoist client: {e}") from e

    def validate_connection(self) -> bool:
        """Validate the API connection and token.

        Returns:
            True if connection is valid

        Raises:
            TodoistError: If connection fails
        """
        try:
            # Try to get projects as a simple validation
            self._api.get_projects()
            logger.info("Todoist connection validated successfully")
            return True
        except Exception as e:
            raise TodoistError(
                f"Failed to connect to Todoist. Check your API token: {e}"
            ) from e

    def _load_projects_cache(self) -> None:
        """Load projects into cache."""
        if self._projects_cache is not None:
            return

        try:
            projects = self._api.get_projects()
            self._projects_cache = {project.name.lower(): project.id for project in projects}
            logger.debug(f"Loaded {len(self._projects_cache)} projects into cache")
        except Exception as e:
            logger.warning(f"Failed to load projects cache: {e}")
            self._projects_cache = {}

    def get_project_id(self, project_name: str) -> Optional[str]:
        """Get project ID by name.

        Args:
            project_name: Project name to lookup

        Returns:
            Project ID if found, None otherwise
        """
        self._load_projects_cache()
        return self._projects_cache.get(project_name.lower())

    def _load_sections_cache(self, project_id: str) -> None:
        """Load sections for a project into cache.

        Args:
            project_id: Project ID to load sections for
        """
        if project_id in self._sections_cache:
            return

        try:
            sections = self._api.get_sections(project_id=project_id)
            self._sections_cache[project_id] = {
                section.name.lower(): section.id for section in sections
            }
            logger.debug(f"Loaded {len(self._sections_cache[project_id])} sections for project {project_id}")
        except Exception as e:
            logger.warning(f"Failed to load sections for project {project_id}: {e}")
            self._sections_cache[project_id] = {}

    def get_section_id(self, project_id: str, section_name: str) -> Optional[str]:
        """Get section ID by name within a project.

        Args:
            project_id: Project ID
            section_name: Section name to lookup

        Returns:
            Section ID if found, None otherwise
        """
        self._load_sections_cache(project_id)
        return self._sections_cache.get(project_id, {}).get(section_name.lower())

    def _build_due_params(self, todo: TodoIntent) -> dict:
        """Build due date parameters for Todoist API.

        Priority:
        1. If due_string (recurring) → use due_string (let Todoist parse)
        2. If due_date + due_time → use due_datetime (RFC3339 UTC)
        3. If due_date only → use due_date (YYYY-MM-DD)
        4. Else → no due date

        Args:
            todo: TodoIntent with date/time information

        Returns:
            Dictionary with appropriate due_* parameter
        """
        if todo.due_string:
            # Recurring tasks - trust Todoist's natural language parser
            logger.debug(f"Using due_string for recurring task: {todo.due_string}")
            return {"due_string": todo.due_string}

        elif todo.due_date and todo.due_time:
            # Combine date and time, convert to UTC RFC3339 format
            try:
                # Parse the date and time
                dt_str = f"{todo.due_date} {todo.due_time}"
                dt_local = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

                # Assume local timezone (system timezone)
                # In future: could get user's timezone from Todoist API or config
                dt_local = dt_local.replace(tzinfo=datetime.now().astimezone().tzinfo)

                # Convert to UTC
                dt_utc = dt_local.astimezone(timezone.utc)

                # Format as RFC3339
                due_datetime = dt_utc.isoformat()
                logger.debug(f"Using due_datetime: {due_datetime} (from {dt_str})")
                return {"due_datetime": due_datetime}

            except ValueError as e:
                logger.warning(f"Failed to parse date/time '{todo.due_date} {todo.due_time}': {e}")
                # Fallback to date only
                if todo.due_date:
                    logger.debug(f"Falling back to due_date: {todo.due_date}")
                    return {"due_date": todo.due_date}
                return {}

        elif todo.due_date:
            # Date only - no time component
            logger.debug(f"Using due_date: {todo.due_date}")
            return {"due_date": todo.due_date}

        return {}

    def find_task_by_name(self, name: str, project_id: Optional[str] = None) -> Optional[str]:
        """Find a task ID by searching for its name.

        Args:
            name: Task name to search for
            project_id: Optional project ID to narrow search

        Returns:
            Task ID if found, None otherwise
        """
        try:
            tasks = self._api.get_tasks(project_id=project_id) if project_id else self._api.get_tasks()
            name_lower = name.lower()

            for task in tasks:
                if task.content.lower() == name_lower or name_lower in task.content.lower():
                    logger.debug(f"Found matching task: {task.content} (ID: {task.id})")
                    return task.id

            logger.debug(f"No task found matching '{name}'")
            return None
        except Exception as e:
            logger.warning(f"Failed to search for task '{name}': {e}")
            return None

    def create_task(self, todo: TodoIntent) -> Task:
        """Create a task in Todoist from TodoIntent.

        Args:
            todo: TodoIntent with task information

        Returns:
            Created Task object

        Raises:
            TodoistError: If task creation fails
        """
        try:
            logger.info(f"Creating Todoist task: {todo.title}")

            # Map priority (Paula 1-4 -> Todoist 4-1)
            todoist_priority = self.PRIORITY_MAP.get(todo.priority, 1)

            # Get project ID if project name specified
            project_id = None
            if todo.project_name:
                project_id = self.get_project_id(todo.project_name)
                if not project_id:
                    logger.warning(
                        f"Project '{todo.project_name}' not found, "
                        "task will be created in Inbox"
                    )

            # Get section ID if section name specified (requires project)
            section_id = None
            if todo.section_name and project_id:
                section_id = self.get_section_id(project_id, todo.section_name)
                if not section_id:
                    logger.warning(
                        f"Section '{todo.section_name}' not found in project, "
                        "task will be created without section"
                    )

            # Get parent task ID if parent task name specified
            parent_id = None
            if todo.parent_task_name:
                parent_id = self.find_task_by_name(todo.parent_task_name, project_id)
                if not parent_id:
                    logger.warning(
                        f"Parent task '{todo.parent_task_name}' not found, "
                        "task will be created as a top-level task"
                    )

            # Build due date parameters
            due_params = self._build_due_params(todo)

            # Build duration parameters with hour → minute conversion
            duration_value = None
            duration_unit_value = None
            if todo.duration and todo.duration_unit:
                if todo.duration_unit == "hour":
                    # Convert hours to minutes (API only supports minute and day)
                    duration_value = todo.duration * 60
                    duration_unit_value = "minute"
                    logger.debug(f"Converted {todo.duration} hour(s) to {duration_value} minutes")
                else:
                    duration_value = todo.duration
                    duration_unit_value = todo.duration_unit

            # Create the task with all available parameters
            task = self._api.add_task(
                content=todo.title,
                description=todo.description,
                project_id=project_id,
                section_id=section_id,
                parent_id=parent_id,
                priority=todoist_priority,
                labels=todo.labels,
                duration=duration_value,
                duration_unit=duration_unit_value,
                **due_params,  # Unpack due_string, due_date, or due_datetime
            )

            logger.info(f"Task created successfully: {task.id}")
            logger.debug(f"Task URL: {task.url}")

            return task

        except Exception as e:
            raise TodoistError(f"Failed to create task: {e}") from e

    def get_task_url(self, task: Task) -> str:
        """Get the web URL for a task.

        Args:
            task: Task object

        Returns:
            Task URL
        """
        return task.url if hasattr(task, "url") else f"https://todoist.com/app/task/{task.id}"
