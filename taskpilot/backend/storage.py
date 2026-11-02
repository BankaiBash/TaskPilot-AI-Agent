"""Persistent JSON storage layer for TaskPilot tasks and agent activity logs."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
ACTIVITY_FILE = DATA_DIR / "activity.json"

_storage_lock = threading.Lock()


def _ensure_data_files() -> None:
    """Ensure the data directory and JSON files exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("[]", encoding="utf-8")
    if not ACTIVITY_FILE.exists():
        ACTIVITY_FILE.write_text("[]", encoding="utf-8")


def _read_json_list(filepath: Path) -> List[Dict[str, Any]]:
    _ensure_data_files()
    try:
        raw = filepath.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_json_list(filepath: Path, data: List[Dict[str, Any]]) -> None:
    _ensure_data_files()
    temp_file = filepath.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(filepath)


def _generate_task_id(existing_tasks: List[Dict[str, Any]]) -> str:
    """Generate a human-friendly unique task ID (e.g., TSK-1004)."""
    existing_ids = {str(t.get("id", "")) for t in existing_tasks}
    max_num = 1000
    for tid in existing_ids:
        if tid.startswith("TSK-"):
            suffix = tid[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    candidate = f"TSK-{max_num + 1}"
    while candidate in existing_ids:
        candidate = f"TSK-{uuid.uuid4().hex[:6].upper()}"
    return candidate


def load_tasks(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all tasks, optionally filtered by completion status ('all', 'active', 'completed')."""
    with _storage_lock:
        tasks = _read_json_list(TASKS_FILE)

    if status_filter:
        normalized = status_filter.strip().lower()
        if normalized in ("completed", "done", "true"):
            tasks = [t for t in tasks if bool(t.get("completed"))]
        elif normalized in ("active", "pending", "incomplete", "false", "todo"):
            tasks = [t for t in tasks if not bool(t.get("completed"))]

    return tasks


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Look up a single task by its unique ID (case-insensitive match supported)."""
    if not task_id or not isinstance(task_id, str):
        return None
    target = task_id.strip().upper()
    with _storage_lock:
        tasks = _read_json_list(TASKS_FILE)
        for task in tasks:
            if str(task.get("id", "")).upper() == target:
                return task
    return None


def create_task(name: str, deadline: str) -> Dict[str, Any]:
    """Create and persist a new task in tasks.json."""
    clean_name = (name or "").strip()
    clean_deadline = (deadline or "").strip() or "No deadline specified"
    if not clean_name:
        raise ValueError("Task name cannot be empty.")

    with _storage_lock:
        tasks = _read_json_list(TASKS_FILE)
        new_task: Dict[str, Any] = {
            "id": _generate_task_id(tasks),
            "name": clean_name,
            "deadline": clean_deadline,
            "completed": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        tasks.append(new_task)
        _write_json_list(TASKS_FILE, tasks)
        return new_task


def update_task(
    task_id: str,
    *,
    name: Optional[str] = None,
    deadline: Optional[str] = None,
    completed: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Update fields on an existing task and save to tasks.json."""
    if not task_id or not isinstance(task_id, str):
        return None
    target = task_id.strip().upper()

    with _storage_lock:
        tasks = _read_json_list(TASKS_FILE)
        for task in tasks:
            if str(task.get("id", "")).upper() == target:
                if name is not None:
                    clean_name = name.strip()
                    if not clean_name:
                        raise ValueError("Task name cannot be empty.")
                    task["name"] = clean_name
                if deadline is not None:
                    task["deadline"] = deadline.strip() or "No deadline specified"
                if completed is not None:
                    task["completed"] = bool(completed)
                task["updated_at"] = datetime.now().isoformat(timespec="seconds")
                _write_json_list(TASKS_FILE, tasks)
                return task
    return None


def remove_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Delete a task by its unique ID and return the deleted task dict if found."""
    if not task_id or not isinstance(task_id, str):
        return None
    target = task_id.strip().upper()

    with _storage_lock:
        tasks = _read_json_list(TASKS_FILE)
        for index, task in enumerate(tasks):
            if str(task.get("id", "")).upper() == target:
                deleted = tasks.pop(index)
                _write_json_list(TASKS_FILE, tasks)
                return deleted
    return None


def record_activity(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Record an execution timeline / activity entry (keeps the most recent 100 entries)."""
    with _storage_lock:
        activities = _read_json_list(ACTIVITY_FILE)
        record = {
            "id": entry.get("id") or f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": entry.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
            **entry,
        }
        activities.insert(0, record)
        activities = activities[:100]
        _write_json_list(ACTIVITY_FILE, activities)
        return record


def load_activities(limit: int = 30) -> List[Dict[str, Any]]:
    """Return the most recent agent activity logs."""
    with _storage_lock:
        activities = _read_json_list(ACTIVITY_FILE)
    return activities[: max(1, min(limit, 100))]
