"""Comprehensive automated tests for TaskPilot backend: storage, tools, agent loop, and API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest
from google.genai import types

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import agent
import main
import storage
import tools


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect storage files to a temporary directory for every test."""
    test_tasks_file = tmp_path / "tasks.json"
    test_activity_file = tmp_path / "activity.json"
    initial_tasks = [
        {
            "id": "TSK-1001",
            "name": "Initial Seed Task",
            "deadline": "2026-11-05 18:00",
            "completed": False,
            "created_at": "2026-11-02T10:00:00",
        }
    ]
    test_tasks_file.write_text(json.dumps(initial_tasks), encoding="utf-8")
    test_activity_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "TASKS_FILE", test_tasks_file)
    monkeypatch.setattr(storage, "ACTIVITY_FILE", test_activity_file)
    yield


def test_calculator_tool_safe_and_accurate():
    res1 = tools.calculator("(150 * 3) + sqrt(144) - 12")
    assert res1["success"] is True
    assert res1["result"] == 450

    # Division by zero handled gracefully
    res_zero = tools.calculator("100 / 0")
    assert res_zero["success"] is False
    assert "Division by zero" in res_zero["error"]

    # Code injection / unrestricted eval attempt blocked
    res_malicious = tools.calculator("__import__('os').system('echo hacked')")
    assert res_malicious["success"] is False

    # Huge exponent blocked
    res_exp = tools.calculator("10 ** 5000")
    assert res_exp["success"] is False
    assert "safety limit" in res_exp["error"]


def test_task_crud_and_confirmation_guard():
    # Add task
    added = tools.add_task(name="Deploy FastAPI server", deadline="2026-11-06 09:00")
    assert added["success"] is True
    new_id = added["task"]["id"]
    assert new_id == "TSK-1002"

    # View tasks
    all_tasks = tools.view_tasks("all")
    assert all_tasks["success"] is True
    assert all_tasks["count"] == 2

    # Unconfirmed delete must NOT delete the task
    del_unconfirmed = tools.delete_task(new_id, confirmed=False)
    assert del_unconfirmed["success"] is False
    assert del_unconfirmed["requires_confirmation"] is True
    assert storage.get_task(new_id) is not None

    # Confirmed delete removes the task
    del_confirmed = tools.delete_task(new_id, confirmed=True)
    assert del_confirmed["success"] is True
    assert storage.get_task(new_id) is None


def test_current_datetime_tool():
    dt = tools.get_current_datetime()
    assert dt["success"] is True
    assert "iso" in dt
    assert "readable" in dt
    assert "weekday" in dt


def _make_fc_response(tool_calls: List[tuple[str, dict[str, Any]]]) -> MagicMock:
    """Helper to construct a mock Gemini GenerateContentResponse with function_calls."""
    parts = [
        types.Part.from_function_call(name=name, args=args)
        for name, args in tool_calls
    ]
    content = types.Content(role="model", parts=parts)
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.function_calls = [p.function_call for p in parts]
    resp.text = None
    return resp


def _make_text_response(text: str) -> MagicMock:
    """Helper to construct a mock Gemini GenerateContentResponse with final text."""
    part = types.Part.from_text(text=text)
    content = types.Content(role="model", parts=[part])
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.function_calls = []
    resp.text = text
    return resp


def test_agent_multi_tool_execution_loop_and_learning_mode():
    """Verify the 9-step agent loop chains get_current_datetime -> calculator -> add_task."""
    fake_client = MagicMock()
    fake_client.models.list.return_value = []

    # Turn 1: Gemini calls get_current_datetime and calculator
    # Turn 2: Gemini receives both function responses and calls add_task
    # Turn 3: Gemini receives add_task response and outputs final answer
    fake_client.models.generate_content.side_effect = [
        _make_fc_response(
            [
                ("get_current_datetime", {}),
                ("calculator", {"expression": "1200 * 1.18"}),
            ]
        ),
        _make_fc_response(
            [
                ("add_task", {"name": "Pay invoice of $1416", "deadline": "2026-11-03 17:00"}),
            ]
        ),
        _make_text_response(
            "I checked the current date, calculated 1200 * 1.18 = 1416, and added the task 'Pay invoice of $1416' for tomorrow."
        ),
    ]

    pilot = agent.TaskPilotAgent(client=fake_client)
    result = pilot.run("Calculate 1200 * 1.18 and add a task to pay that invoice tomorrow at 5pm")

    assert result["success"] is True
    assert len(result["tool_calls"]) == 3
    assert [t["tool_name"] for t in result["tool_calls"]] == [
        "get_current_datetime",
        "calculator",
        "add_task",
    ]
    assert result["tool_calls"][1]["result"]["result"] == 1416
    assert "1416" in result["response"]

    # Verify Learning Mode structure
    lm = result["learning_mode"]
    assert "user_requested" in lm
    assert "gemini_understood" in lm
    assert len(lm["steps"]) == 3
    assert lm["steps"][1]["tool_name"] == "calculator"


def test_agent_destructive_delete_requires_human_approval():
    """Verify the agent cannot bypass confirmation even if Gemini attempts to pass confirmed=True."""
    fake_client = MagicMock()
    fake_client.models.list.return_value = []
    fake_client.models.generate_content.side_effect = [
        _make_fc_response([("delete_task", {"task_id": "TSK-1001", "confirmed": True})]),
        _make_text_response("Please confirm if you want me to permanently delete TSK-1001."),
    ]

    pilot = agent.TaskPilotAgent(client=fake_client)
    res_unconfirmed = pilot.run("Delete task TSK-1001")
    assert len(res_unconfirmed["pending_confirmations"]) == 1
    assert res_unconfirmed["pending_confirmations"][0]["id"] == "TSK-1001"
    assert storage.get_task("TSK-1001") is not None

    # Now simulate user clicking Confirm Deletion in the UI
    fake_client.models.generate_content.side_effect = [
        _make_fc_response([("delete_task", {"task_id": "TSK-1001"})]),
        _make_text_response("Task TSK-1001 has been permanently deleted."),
    ]
    res_confirmed = pilot.run(
        "Confirm deletion of task TSK-1001",
        confirmed_delete_ids=["TSK-1001"],
    )
    assert res_confirmed["success"] is True
    assert res_confirmed["pending_confirmations"] == []
    assert storage.get_task("TSK-1001") is None


def test_agent_max_iteration_limit():
    """Verify the agent stops safely at MAX_TOOL_ITERATIONS."""
    fake_client = MagicMock()
    fake_client.models.list.return_value = []
    fake_client.models.generate_content.side_effect = [
        _make_fc_response([("get_current_datetime", {})])
        for _ in range(agent.MAX_TOOL_ITERATIONS + 2)
    ]

    pilot = agent.TaskPilotAgent(client=fake_client)
    res = pilot.run("Loop forever")
    assert res["iterations"] == agent.MAX_TOOL_ITERATIONS
    assert len(res["tool_calls"]) == agent.MAX_TOOL_ITERATIONS
    assert any(step["type"] == "iteration_limit" for step in res["timeline"])


def _asgi_request(
    method: str,
    path: str,
    *,
    query: str = "",
    json_body: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Drive FastAPI's full ASGI stack in-process without opening Windows loopback socketpairs."""
    raw_body = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query.encode("utf-8"),
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(raw_body)).encode("utf-8")),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent_messages: List[Dict[str, Any]] = []
    request_delivered = False

    async def receive() -> Dict[str, Any]:
        nonlocal request_delivered
        if not request_delivered:
            request_delivered = True
            return {"type": "http.request", "body": raw_body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Dict[str, Any]) -> None:
        sent_messages.append(message)

    coro = main.app(scope, receive, send)
    try:
        while True:
            coro.send(None)
    except StopIteration:
        pass

    status_code = next(
        m["status"] for m in sent_messages if m["type"] == "http.response.start"
    )
    body_bytes = b"".join(
        m.get("body", b"") for m in sent_messages if m["type"] == "http.response.body"
    )
    return status_code, json.loads(body_bytes.decode("utf-8"))


def test_fastapi_endpoints(monkeypatch: pytest.MonkeyPatch):
    # GET /health
    status_health, data_health = _asgi_request("GET", "/health")
    assert status_health == 200
    assert data_health["status"] == "ok"

    # GET /tasks
    status_tasks, data_tasks = _asgi_request("GET", "/tasks")
    assert status_tasks == 200
    assert data_tasks["total_count"] == 1

    # POST /tasks
    status_create, data_create = _asgi_request(
        "POST", "/tasks", json_body={"name": "Write README", "deadline": "Tonight"}
    )
    assert status_create == 201
    created_id = data_create["task"]["id"]

    # PATCH /tasks/{task_id}
    status_patch, data_patch = _asgi_request(
        "PATCH", f"/tasks/{created_id}", json_body={"completed": True}
    )
    assert status_patch == 200
    assert data_patch["task"]["completed"] is True

    # DELETE /tasks/{task_id} without confirmation -> 400
    status_del_unconf, _ = _asgi_request("DELETE", f"/tasks/{created_id}")
    assert status_del_unconf == 400

    # DELETE /tasks/{task_id}?confirmed=true -> 200
    status_del_conf, _ = _asgi_request(
        "DELETE", f"/tasks/{created_id}", query="confirmed=true"
    )
    assert status_del_conf == 200

    # GET /activity
    status_act, data_act = _asgi_request("GET", "/activity")
    assert status_act == 200
    assert len(data_act["activities"]) >= 3

    # POST /chat via FastAPI route with mocked Gemini client
    fake_client = MagicMock()
    fake_client.models.list.return_value = []
    fake_client.models.generate_content.side_effect = [
        _make_fc_response([("calculator", {"expression": "42 * 2"})]),
        _make_text_response("42 multiplied by 2 is 84."),
    ]
    monkeypatch.setattr(main.agent_instance, "_injected_client", fake_client)

    status_chat, data_chat = _asgi_request(
        "POST", "/chat", json_body={"message": "What is 42 * 2?", "history": []}
    )
    assert status_chat == 200
    assert data_chat["success"] is True
    assert data_chat["tool_calls"][0]["result"]["result"] == 84
    assert "84" in data_chat["response"]
