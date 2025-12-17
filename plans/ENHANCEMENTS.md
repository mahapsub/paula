# Paula Enhancements - Smart Task Detection & Rich Todoist Integration

## Completed Enhancements

### Phase 1: Enhanced TodoIntent Model ✅
**File:** `src/paula/intent/ollama_service.py`

Added comprehensive fields to TodoIntent:
- `is_task` - Boolean to detect if transcription contains a task
- `confidence` - Confidence score (0.0-1.0)
- `section_name` - Section within project
- `due_time` - Specific time in HH:MM format
- `due_string` - Natural language for recurring tasks
- `deadline_date` - Separate hard deadline
- `duration` & `duration_unit` - Time estimates
- `parent_task_name` & `is_subtask` - Task hierarchy
- `notes` - Additional context

### Phase 2: Enhanced LLM Prompt ✅
**File:** `src/paula/intent/prompts.py`

Completely rewrote the prompt to:
- **First determine if it's a task** with confidence score
- Extract ALL 19 fields comprehensively
- Includes examples for:
  - Non-tasks ("just testing", "hmm what to do")
  - Simple tasks ("buy milk")
  - Complex tasks with time, duration, project, section
  - Recurring tasks ("every morning")
  - Tasks with deadlines

### Phase 3: Enhanced Todoist Client ✅
**File:** `src/paula/todoist/client.py`

Added new capabilities:
- **Section caching** - Maps section names to IDs within projects
- **Task lookup** - Finds parent tasks by name
- **Enhanced create_task()** - Uses ALL new TodoIntent fields:
  - Sections, parent tasks, durations
  - Specific times (date + time)
  - Recurring patterns via due_string
  - Separate deadlines
  - Proper description parameter

### Phase 4: Enhanced CLI ✅
**File:** `src/paula/cli.py`

Added intelligent task handling:
- **Detects non-tasks** - Shows "Not a task detected" message
- **Option to create anyway** - Prompts user for title if they want to proceed
- **Rich display of ALL extracted fields**:
  - Shows confidence score
  - Displays all time info (due date/time, recurring, deadline)
  - Shows organization (project, section, labels)
  - Shows hierarchy (parent task, subtask status)
  - Shows duration estimates
- **Visual indicators** with emojis for better UX

## What's New

### 1. Smart Task Detection
```
User says: "just testing"
Paula: ℹ️  Not a task detected (confidence: 95%)
       User was testing their microphone
       You said: "just testing"
```

### 2. Comprehensive Task Extraction
```
User says: "schedule dentist next Tuesday at 3pm for 30 minutes in health project"

Paula extracts:
  - is_task: true (98% confident)
  - title: "Dentist appointment"
  - due_date: "2025-12-23"
  - due_time: "15:00"
  - duration: 30 minutes
  - project_name: "health"

Creates task with ALL this information in Todoist!
```

### 3. Rich Organization
```
User says: "add review code to work project in urgent section"

Paula extracts:
  - title: "Review code"
  - project_name: "work"
  - section_name: "urgent"
  - priority: 2 (High)

Places task in correct project AND section!
```

### 4. Recurring Tasks
```
User says: "remind me to take vitamins every morning"

Paula extracts:
  - title: "Take vitamins"
  - due_string: "every morning"

Creates recurring task in Todoist!
```

## Testing

Try these examples:

**Non-task:**
- "just testing the microphone"
- "hmm what should I do today"

**Simple task:**
- "buy milk"

**Complex task:**
- "schedule dentist appointment next Tuesday at 3pm for 30 minutes in health project"

**With section:**
- "add review code to work project in urgent section"

**Recurring:**
- "remind me to take vitamins every morning"

**With deadline:**
- "finish report by Friday with hard deadline Monday"

## Technical Details

**No new dependencies** - Uses existing Todoist API v2 capabilities

**Enhanced fields used:**
- Task detection (is_task, confidence)
- Organization (section_id, parent_id)
- Time (due_string for datetime & recurring, duration)
- Metadata (description as separate field, not in content)

**Graceful degradation:**
- If section not found: creates without section
- If parent task not found: creates as top-level task
- If project not found: creates in Inbox

All with appropriate warnings in logs.
