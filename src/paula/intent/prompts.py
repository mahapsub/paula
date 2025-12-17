"""LLM prompt templates for intent extraction."""

INTENT_EXTRACTION_PROMPT = """You are a JSON extraction assistant. Your ONLY job is to output valid JSON - no code, no explanations, just JSON.

User said: "{transcription}"

Extract task information and return as JSON with these fields:
- title: Brief task description (required)
- description: Additional details (or null)
- priority: 1 (urgent), 2 (high), 3 (medium), or 4 (normal) - default to 4
- due_date: Date in YYYY-MM-DD format (or null if not mentioned). Today is 2025-12-16.
- project_name: Project name (or null)
- labels: Array of labels (or empty array [])

CRITICAL: Return ONLY the JSON object. Do not include any code, comments, or explanations.

Examples:

User: "Remind me to call mom tomorrow at 2pm"
{{"title": "Call mom", "description": "at 2pm", "priority": 4, "due_date": "2025-12-17", "project_name": null, "labels": []}}

User: "Urgent: finish the quarterly report by Friday"
{{"title": "Finish quarterly report", "description": null, "priority": 1, "due_date": "2025-12-20", "project_name": null, "labels": []}}

User: "Add buy groceries to my personal project"
{{"title": "Buy groceries", "description": null, "priority": 4, "due_date": null, "project_name": "personal", "labels": []}}

Now extract from the user's input above. Return ONLY JSON:"""


def format_intent_prompt(transcription: str) -> str:
    """Format the intent extraction prompt with transcription.

    Args:
        transcription: Transcribed text from speech

    Returns:
        Formatted prompt ready for LLM
    """
    return INTENT_EXTRACTION_PROMPT.format(transcription=transcription)
