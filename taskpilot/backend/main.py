"""FastAPI Backend for TaskPilot AI Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import storage
from agent import agent_instance

app = FastAPI(
    title="TaskPilot AI Agent API",
    description="Backend API for TaskPilot — An educational & action-oriented Gemini Function-Calling AI Agent.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatHistoryItem(BaseModel):
    role: str = Field(..., description="Role of the speaker ('user' or 'agent')")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Natural-language message from the user")
    history: List[ChatHistoryItem] = Field(default_factory=list, description="Recent conversation history")
    confirmed_delete_ids: List[str] = Field(
        default_factory=list,
        description="List of task IDs explicitly confirmed by the human user for deletion",
    )


class CreateTaskRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Task title")
    deadline: str = Field(default="No deadline specified", max_length=100, description="Task deadline")


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    deadline: Optional[str] = Field(default=None, max_length=100)
    completed: Optional[bool] = Field(default=None)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """Return service health and agent status."""
    return {
        "status": "ok",
        "agent": agent_instance.get_status(),
    }


@app.post("/chat", status_code=status.HTTP_200_OK)
async def chat_endpoint(payload: ChatRequest) -> Dict[str, Any]:
    """Process a natural-language user message through the TaskPilot Gemini Agent."""
    clean_msg = payload.message.strip()
    if not clean_msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only.",
        )

    history_dicts = [{"role": item.role, "content": item.content} for item in payload.history]
    result = agent_instance.run(
        user_message=clean_msg,
        history=history_dicts,
        confirmed_delete_ids=payload.confirmed_delete_ids,
    )
    return result


@app.get("/tasks", status_code=status.HTTP_200_OK)
async def get_tasks_endpoint(
    status_filter: Optional[str] = Query(default="all", alias="status", description="Filter: all, active, completed")
) -> Dict[str, Any]:
    """Retrieve all saved tasks, optionally filtered by completion status."""
    tasks = storage.load_tasks(status_filter=status_filter)
    all_tasks = storage.load_tasks(status_filter="all")
    active_count = sum(1 for t in all_tasks if not t.get("completed"))
    completed_count = sum(1 for t in all_tasks if t.get("completed"))
    return {
        "success": True,
        "filter": status_filter or "all",
        "count": len(tasks),
        "active_count": active_count,
        "completed_count": completed_count,
        "total_count": len(all_tasks),
        "tasks": tasks,
    }


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task_endpoint(payload: CreateTaskRequest) -> Dict[str, Any]:
    """Create a new task directly and persist to JSON storage."""
    try:
        created = storage.create_task(name=payload.name, deadline=payload.deadline)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    storage.record_activity(
        {
            "user_request": f"UI Action: Created task '{created['name']}'",
            "status": "completed",
            "model": "Direct UI Action",
            "tools_used": ["add_task"],
            "timeline": [
                {
                    "step": 1,
                    "type": "user_request",
                    "title": "Direct Task Creation",
                    "detail": f"Created task '{created['name']}' via Task Manager UI.",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                },
                {
                    "step": 2,
                    "type": "python_execution",
                    "title": "Task Persisted to JSON",
                    "detail": f"Saved {created['id']} with deadline '{created['deadline']}'.",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                },
            ],
            "final_response": f"Task '{created['name']}' ({created['id']}) saved.",
            "duration_ms": 5,
        }
    )
    return {
        "success": True,
        "message": f"Task '{created['name']}' created successfully.",
        "task": created,
    }


@app.patch("/tasks/{task_id}", status_code=status.HTTP_200_OK)
async def update_task_endpoint(task_id: str, payload: UpdateTaskRequest) -> Dict[str, Any]:
    """Update task completion status, name, or deadline."""
    try:
        updated = storage.update_task(
            task_id,
            name=payload.name,
            deadline=payload.deadline,
            completed=payload.completed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    state_label = "completed" if updated.get("completed") else "active"
    storage.record_activity(
        {
            "user_request": f"UI Action: Updated task {updated['id']} ({state_label})",
            "status": "completed",
            "model": "Direct UI Action",
            "tools_used": ["patch_task"],
            "timeline": [
                {
                    "step": 1,
                    "type": "user_request",
                    "title": "Task Status Updated",
                    "detail": f"Marked '{updated['name']}' ({updated['id']}) as {state_label}.",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                }
            ],
            "final_response": f"Task {updated['id']} updated to {state_label}.",
            "duration_ms": 4,
        }
    )
    return {
        "success": True,
        "message": f"Task '{updated['id']}' updated.",
        "task": updated,
    }


@app.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task_endpoint(
    task_id: str,
    confirmed: bool = Query(
        default=False,
        description="Must be true to confirm permanent deletion of the task.",
    ),
) -> Dict[str, Any]:
    """Delete a task by its unique ID. Requires confirmed=true."""
    existing = storage.get_task(task_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "requires_confirmation": True,
                "message": f"Confirmation required before deleting task '{existing['name']}' ({existing['id']}). Pass ?confirmed=true after user approval.",
                "task": existing,
            },
        )

    deleted = storage.remove_task(task_id)
    storage.record_activity(
        {
            "user_request": f"Confirmed Deletion: Task {existing['id']} ('{existing['name']}')",
            "status": "completed",
            "model": "Human-Confirmed Action",
            "tools_used": ["delete_task"],
            "timeline": [
                {
                    "step": 1,
                    "type": "user_request",
                    "title": "Human Approval Confirmed",
                    "detail": f"User confirmed deletion of '{existing['name']}' ({existing['id']}).",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                },
                {
                    "step": 2,
                    "type": "python_execution",
                    "title": "Task Removed from Storage",
                    "detail": f"Deleted {existing['id']} from data/tasks.json.",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                },
            ],
            "final_response": f"Task '{existing['name']}' ({existing['id']}) permanently deleted.",
            "duration_ms": 5,
        }
    )
    return {
        "success": True,
        "message": f"Task '{existing['name']}' ({existing['id']}) deleted.",
        "deleted_task": deleted,
    }


@app.get("/activity", status_code=status.HTTP_200_OK)
async def get_activity_endpoint(limit: int = Query(default=25, ge=1, le=100)) -> Dict[str, Any]:
    """Retrieve the agent execution timeline logs, agent status, and task summary counts."""
    activities = storage.load_activities(limit=limit)
    all_tasks = storage.load_tasks(status_filter="all")
    active_count = sum(1 for t in all_tasks if not t.get("completed"))
    completed_count = sum(1 for t in all_tasks if t.get("completed"))

    return {
        "success": True,
        "agent": agent_instance.get_status(),
        "metrics": {
            "active_tasks": active_count,
            "completed_tasks": completed_count,
            "total_tasks": len(all_tasks),
            "total_activities": len(activities),
        },
        "activities": activities,
    }


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
