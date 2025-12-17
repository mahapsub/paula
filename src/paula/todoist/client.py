"""Todoist API client for Paula."""

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

            # Build task content
            content = todo.title
            if todo.description:
                # Todoist doesn't have separate description field in simple task creation
                # We'll add it to the content in parentheses
                content = f"{todo.title} ({todo.description})"

            # Create the task
            task = self._api.add_task(
                content=content,
                project_id=project_id,
                priority=todoist_priority,
                due_string=todo.due_date if todo.due_date else None,
                labels=todo.labels,
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
