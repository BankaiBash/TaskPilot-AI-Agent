"""TaskPilot AI Agent powered by Google Gemini (google-genai SDK) and Function Calling."""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

import storage
import tools

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger("taskpilot.agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)

MAX_TOOL_ITERATIONS = 6

SYSTEM_INSTRUCTION = """You are TaskPilot, an intelligent, precise, and action-oriented AI Agent built to help users manage tasks, perform calculations, and reason through multi-step workflows.

Core Operating Principles:
1. You have access to 5 real backend tools:
   - `calculator`: Evaluate mathematical expressions safely. Always use this for any arithmetic or formula instead of guessing.
   - `add_task`: Create and persist a new task with a `name` and `deadline`.
   - `view_tasks`: Retrieve saved tasks (`all`, `active`, or `completed`).
   - `delete_task`: Delete a task by its unique ID (e.g., `TSK-1001`). Note: Deletion is a destructive action and requires human confirmation.
   - `get_current_datetime`: Retrieve the real system date, time, weekday, and timezone.

2. Multi-Tool Chaining:
   - If a user asks to add a task with a relative deadline (e.g., "tomorrow at 5pm", "next Friday", "in 2 hours"), FIRST call `get_current_datetime` to know the exact current date and time, then call `add_task` with the resolved deadline.
   - If a user asks to delete a task by its name rather than its ID (e.g., "Delete the sprint budget task"), FIRST call `view_tasks` to look up the task's unique ID, then call `delete_task` with that ID.
   - If a user asks a question combining math and task creation (e.g., "Calculate 18% tax on 2450 and add a task to pay that total tomorrow"), call `calculator` and `get_current_datetime`, then call `add_task` with the computed result.

3. Honesty & Precision:
   - Never pretend a tool succeeded if it returned `"success": false` or `"requires_confirmation": true`.
   - When `delete_task` returns `"requires_confirmation": true`, clearly inform the user which task (name and ID) is queued for deletion and ask them to click the Confirm Deletion button to finalize it.
   - Keep responses clear, well-structured, and helpful.
"""


class TaskPilotAgent:
    """Orchestrates the Gemini Function-Calling execution loop, logging, and Learning Mode traces."""

    def __init__(self, client: Optional[genai.Client] = None) -> None:
        self._injected_client = client
        self._resolved_model: Optional[str] = None

    def _get_api_key(self) -> Optional[str]:
        load_dotenv(override=True)
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if key and key.strip() and key.strip() != "your_gemini_api_key_here":
            return key.strip()
        return None

    def is_configured(self) -> bool:
        """Check whether a Gemini API key or injected client is available."""
        return self._injected_client is not None or self._get_api_key() is not None

    def _get_client(self) -> genai.Client:
        if self._injected_client is not None:
            return self._injected_client
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. Please add your key to taskpilot/backend/.env "
                "(see .env.example) and restart or retry."
            )
        return genai.Client(api_key=api_key)

    def resolve_model(self, client: Optional[genai.Client] = None) -> str:
        """Dynamically select a current Gemini Flash model supported by the installed SDK."""
        env_model = os.getenv("GEMINI_MODEL", "").strip()
        if env_model:
            return env_model

        if self._resolved_model:
            return self._resolved_model

        preferred_candidates = [
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
        ]

        active_client = client
        if active_client is None and self.is_configured():
            try:
                active_client = self._get_client()
            except Exception:
                active_client = None

        if active_client is not None:
            try:
                available_flash_models: List[str] = []
                for m in active_client.models.list():
                    raw_name = getattr(m, "name", "") or ""
                    short_name = raw_name.replace("models/", "")
                    actions = getattr(m, "supported_actions", None) or []
                    if actions and "generateContent" not in actions:
                        continue
                    lower_name = short_name.lower()
                    if (
                        "gemini" in lower_name
                        and "flash" in lower_name
                        and not any(
                            excl in lower_name
                            for excl in ("8b", "lite", "tts", "image", "audio", "thinking", "exp")
                        )
                    ):
                        available_flash_models.append(short_name)

                for pref in preferred_candidates:
                    if pref in available_flash_models:
                        self._resolved_model = pref
                        return pref

                if available_flash_models:
                    # Pick the highest versioned standard flash model
                    available_flash_models.sort(reverse=True)
                    self._resolved_model = available_flash_models[0]
                    return self._resolved_model
            except Exception as exc:
                logger.debug("Model auto-discovery fallback triggered: %s", exc)

        self._resolved_model = preferred_candidates[0]
        return self._resolved_model

    def get_status(self) -> Dict[str, Any]:
        """Return agent health, configuration state, and active model info."""
        configured = self.is_configured()
        model_name = self.resolve_model()
        return {
            "agent_name": "TaskPilot Core v1.0",
            "status": "online" if configured else "awaiting_api_key",
            "api_key_configured": configured,
            "model": model_name,
            "sdk": "google-genai",
            "max_iterations": MAX_TOOL_ITERATIONS,
            "available_tools": [
                "calculator",
                "add_task",
                "view_tasks",
                "delete_task",
                "get_current_datetime",
            ],
        }

    def run(
        self,
        user_message: str,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        confirmed_delete_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the full 9-step Gemini agent tool-calling loop for a user request."""
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        start_time = time.perf_counter()
        clean_message = (user_message or "").strip()

        if not clean_message:
            raise ValueError("User message cannot be empty.")

        confirmed_set = {
            cid.strip().upper() for cid in (confirmed_delete_ids or []) if isinstance(cid, str) and cid.strip()
        }

        timeline: List[Dict[str, Any]] = []
        tool_Executions: List[Dict[str, Any]] = []
        pending_confirmations: List[Dict[str, Any]] = []

        def add_timeline_step(
            step_type: str,
            title: str,
            detail: str,
            status: str = "completed",
            meta: Optional[Dict[str, Any]] = None,
        ) -> None:
            timeline.append(
                {
                    "step": len(timeline) + 1,
                    "type": step_type,
                    "title": title,
                    "detail": detail,
                    "status": status,
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "meta": meta or {},
                }
            )

        # Step 1: Receive natural-language user request
        add_timeline_step(
            step_type="user_request",
            title="User Request Received",
            detail=f'Received prompt: "{clean_message}"',
            meta={"confirmed_delete_ids": list(confirmed_set)} if confirmed_set else {},
        )

        # Validate client / API key
        try:
            client = self._get_client()
            model_name = self.resolve_model(client)
        except Exception as exc:
            error_msg = str(exc)
            logger.warning("[%s] Agent configuration error: %s", request_id, error_msg)
            add_timeline_step(
                step_type="error",
                title="Configuration Required",
                detail=error_msg,
                status="error",
            )
            learning_data = self._build_learning_summary(
                user_message=clean_message,
                model_name=self.resolve_model(),
                tool_executions=[],
                final_answer=error_msg,
                error=error_msg,
            )
            activity_entry = storage.record_activity(
                {
                    "id": request_id,
                    "user_request": clean_message,
                    "status": "error",
                    "model": self.resolve_model(),
                    "tools_used": [],
                    "timeline": timeline,
                    "final_response": error_msg,
                    "duration_ms": round((time.perf_counter() - start_time) * 1000),
                }
            )
            return {
                "request_id": request_id,
                "success": False,
                "error": error_msg,
                "response": (
                    "⚠️ **Gemini API Key Required**\n\n"
                    "TaskPilot's backend is running, but `GEMINI_API_KEY` is not yet configured in "
                    "`taskpilot/backend/.env`.\n\n"
                    "1. Copy `taskpilot/backend/.env.example` to `taskpilot/backend/.env`\n"
                    "2. Paste your API key from Google AI Studio (`GEMINI_API_KEY=...`)\n"
                    "3. Send your message again (no server restart needed!)."
                ),
                "model": self.resolve_model(),
                "tool_calls": [],
                "timeline": timeline,
                "pending_confirmations": [],
                "learning_mode": learning_data,
                "activity": activity_entry,
                "duration_ms": round((time.perf_counter() - start_time) * 1000),
            }

        # Build conversation contents for Gemini
        contents: List[types.Content] = []
        if history:
            for msg in history[-10:]:
                role = msg.get("role", "user")
                text = (msg.get("content") or "").strip()
                if not text:
                    continue
                gemini_role = "model" if role in ("assistant", "agent", "model") else "user"
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=text)],
                    )
                )

        # If the user just confirmed a task deletion, append explicit context for the agent
        effective_prompt = clean_message
        if confirmed_set:
            ids_str = ", ".join(sorted(confirmed_set))
            effective_prompt = (
                f"{clean_message}\n\n"
                f"[System Note: The human user has explicitly confirmed deletion for task ID(s): {ids_str}. "
                f"Proceed with calling delete_task for {ids_str}.]"
            )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=effective_prompt)],
            )
        )

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[tools.GEMINI_TOOL_DECLARATIONS],
            temperature=0.2,
        )

        add_timeline_step(
            step_type="gemini_analysis",
            title="Gemini Analysed Request",
            detail=f"Model {model_name} evaluated user intent and available tool declarations.",
            meta={"model": model_name},
        )

        final_response_text = ""
        iteration = 0

        try:
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                logger.info("[%s] Gemini generate_content iteration %d (model=%s)", request_id, iteration, model_name)

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )

                # Extract model candidate content and check for function calls
                candidate_content: Optional[types.Content] = None
                if getattr(response, "candidates", None):
                    candidate_content = response.candidates[0].content

                function_calls = getattr(response, "function_calls", None) or []
                if not function_calls and candidate_content and getattr(candidate_content, "parts", None):
                    function_calls = [
                        part.function_call
                        for part in candidate_content.parts
                        if getattr(part, "function_call", None) is not None
                    ]

                if not function_calls:
                    # Step 9: No more tool calls needed; Gemini produced the final natural-language answer
                    final_response_text = (getattr(response, "text", None) or "").strip()
                    if not final_response_text and candidate_content and getattr(candidate_content, "parts", None):
                        text_parts = [
                            getattr(p, "text", "")
                            for p in candidate_content.parts
                            if getattr(p, "text", None)
                        ]
                        final_response_text = "\n".join(text_parts).strip()

                    if not final_response_text:
                        final_response_text = "Request completed."

                    add_timeline_step(
                        step_type="final_response",
                        title="Final Response Generated",
                        detail=f"Gemini synthesized the final natural-language response (iteration {iteration}).",
                        meta={"iterations": iteration},
                    )
                    break

                # Preserve the model's tool-call turn in the conversation history
                if candidate_content is not None:
                    contents.append(candidate_content)
                else:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[
                                types.Part.from_function_call(
                                    name=fc.name,
                                    args=dict(fc.args) if fc.args else {},
                                )
                                for fc in function_calls
                            ],
                        )
                    )

                function_response_parts: List[types.Part] = []

                for fc in function_calls:
                    tool_name = fc.name or "unknown_tool"
                    raw_args = dict(fc.args) if getattr(fc, "args", None) else {}

                    # Step 4 & 5: Tool selected and arguments generated
                    add_timeline_step(
                        step_type="tool_selected",
                        title=f"Selected Tool: {tool_name}",
                        detail=f"Gemini chose `{tool_name}` with arguments: {raw_args}",
                        meta={"tool": tool_name, "arguments": raw_args, "iteration": iteration},
                    )

                    logger.info("[%s] Executing tool '%s' with args=%s", request_id, tool_name, raw_args)
                    tool_start = time.perf_counter()

                    # Step 6: Execute tool through Python backend
                    tool_result = tools.execute_tool(
                        tool_name=tool_name,
                        arguments=raw_args,
                        confirmed_delete_ids=confirmed_set,
                    )
                    tool_duration_ms = round((time.perf_counter() - tool_start) * 1000, 2)

                    logger.info("[%s] Tool '%s' result: %s (%sms)", request_id, tool_name, tool_result, tool_duration_ms)

                    is_confirmation_needed = bool(tool_result.get("requires_confirmation"))
                    is_success = bool(tool_result.get("success"))

                    if is_confirmation_needed and tool_result.get("task"):
                        pending_confirmations.append(tool_result["task"])

                    step_status = (
                        "awaiting_confirmation"
                        if is_confirmation_needed
                        else ("completed" if is_success else "error")
                    )

                    # Step 7: Record Python execution & observable result
                    add_timeline_step(
                        step_type="python_execution",
                        title=f"Python Executed `{tool_name}`",
                        detail=self._summarize_tool_result(tool_name, tool_result),
                        status=step_status,
                        meta={
                            "tool": tool_name,
                            "arguments": raw_args,
                            "result": tool_result,
                            "duration_ms": tool_duration_ms,
                        },
                    )

                    edu_meta = tools.TOOL_EDUCATIONAL_META.get(
                        tool_name,
                        {
                            "title": tool_name,
                            "why_selected": f"Gemini selected `{tool_name}` to fulfill part of your request.",
                            "python_action": f"Executed Python function `{tool_name}` and returned structured JSON.",
                        },
                    )

                    tool_Executions.append(
                        {
                            "iteration": iteration,
                            "tool_name": tool_name,
                            "arguments": raw_args,
                            "result": tool_result,
                            "status": step_status,
                            "duration_ms": tool_duration_ms,
                            "educational": edu_meta,
                        }
                    )

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response=tool_result,
                        )
                    )

                # Return all function responses back to Gemini for the next iteration of the loop
                contents.append(
                    types.Content(
                        role="user",
                        parts=function_response_parts,
                    )
                )

            else:
                # Reached MAX_TOOL_ITERATIONS limit
                logger.warning("[%s] Reached max tool iterations (%d)", request_id, MAX_TOOL_ITERATIONS)
                add_timeline_step(
                    step_type="iteration_limit",
                    title="Maximum Tool Iteration Limit Reached",
                    detail=f"Stopped after {MAX_TOOL_ITERATIONS} tool-calling iterations to prevent infinite loops.",
                    status="warning",
                )
                final_response_text = (
                    f"I completed { len(tool_Executions) } tool step(s), reaching the maximum safety limit of "
                    f"{MAX_TOOL_ITERATIONS} tool-call iterations. Please review the results above or let me know "
                    "how you would like to proceed."
                )

        except genai_errors.APIError as api_err:
            error_detail = f"Gemini API Error ({getattr(api_err, 'code', 'unknown')}): {getattr(api_err, 'message', str(api_err))}"
            logger.error("[%s] %s", request_id, error_detail)
            add_timeline_step(
                step_type="error",
                title="Gemini API Error",
                detail=error_detail,
                status="error",
            )
            return self._build_error_response(
                request_id=request_id,
                user_message=clean_message,
                model_name=model_name,
                error_detail=error_detail,
                tool_executions=tool_Executions,
                timeline=timeline,
                pending_confirmations=pending_confirmations,
                start_time=start_time,
            )
        except Exception as exc:
            error_detail = f"Agent execution error: {exc}"
            logger.exception("[%s] Unexpected agent error", request_id)
            add_timeline_step(
                step_type="error",
                title="Agent Execution Error",
                detail=error_detail,
                status="error",
            )
            return self._build_error_response(
                request_id=request_id,
                user_message=clean_message,
                model_name=model_name,
                error_detail=error_detail,
                tool_executions=tool_Executions,
                timeline=timeline,
                pending_confirmations=pending_confirmations,
                start_time=start_time,
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000)
        learning_data = self._build_learning_summary(
            user_message=clean_message,
            model_name=model_name,
            tool_executions=tool_Executions,
            final_answer=final_response_text,
        )

        activity_entry = storage.record_activity(
            {
                "id": request_id,
                "user_request": clean_message,
                "status": "awaiting_confirmation" if pending_confirmations else "completed",
                "model": model_name,
                "tools_used": [t["tool_name"] for t in tool_Executions],
                "timeline": timeline,
                "final_response": final_response_text,
                "duration_ms": duration_ms,
            }
        )

        return {
            "request_id": request_id,
            "success": True,
            "response": final_response_text,
            "model": model_name,
            "iterations": iteration,
            "tool_calls": tool_Executions,
            "timeline": timeline,
            "pending_confirmations": pending_confirmations,
            "learning_mode": learning_data,
            "activity": activity_entry,
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _summarize_tool_result(tool_name: str, result: Dict[str, Any]) -> str:
        """Create a concise, human-readable summary of a tool's execution output."""
        if result.get("requires_confirmation"):
            task = result.get("task") or {}
            return f"Paused for human approval before deleting '{task.get('name', 'task')}' ({task.get('id', '')})."

        if not result.get("success"):
            return f"Execution failed: {result.get('error', 'Unknown error')}"

        if tool_name == "calculator":
            return f"Computed {result.get('expression')} = {result.get('result')}"
        if tool_name == "add_task":
            task = result.get("task") or {}
            return f"Saved task '{task.get('name')}' (ID: {task.get('id')}, Deadline: {task.get('deadline')})"
        if tool_name == "view_tasks":
            return f"Retrieved {result.get('count', 0)} task(s) (filter: {result.get('filter', 'all')})"
        if tool_name == "delete_task":
            deleted = result.get("deleted_task") or {}
            return f"Deleted task '{deleted.get('name')}' (ID: {deleted.get('id')})"
        if tool_name == "get_current_datetime":
            return f"System clock: {result.get('readable')}"
        return "Function executed successfully."

    @staticmethod
    def _build_learning_summary(
        *,
        user_message: str,
        model_name: str,
        tool_executions: List[Dict[str, Any]],
        final_answer: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build beginner-friendly behind-the-scenes educational explanations for LEARNING MODE."""
        if error:
            return {
                "user_requested": f'You sent the prompt: "{user_message}"',
                "gemini_understood": "The backend received your prompt, but could not complete the Gemini call due to an API or configuration issue.",
                "tools_selected_why": "No tools were executed because the model connection encountered an error.",
                "steps": [],
                "how_final_answer_generated": f"The backend caught the error gracefully and reported: {error}",
            }

        if not tool_executions:
            return {
                "user_requested": f'You sent the prompt: "{user_message}"',
                "gemini_understood": (
                    f"Gemini ({model_name}) analyzed your message and determined that it could be answered "
                    "directly through natural conversation without calling any external backend tools."
                ),
                "tools_selected_why": "No tool was needed because your prompt did not require calculations, system time, or task storage changes.",
                "steps": [],
                "how_final_answer_generated": (
                    "Gemini generated a direct natural-language response in a single turn."
                ),
            }

        tool_names = [t["tool_name"] for t in tool_executions]
        steps_breakdown = []
        for idx, t in enumerate(tool_executions, start=1):
            edu = t.get("educational") or {}
            steps_breakdown.append(
                {
                    "step_number": idx,
                    "tool_name": t["tool_name"],
                    "tool_title": edu.get("title", t["tool_name"]),
                    "why_selected": edu.get("why_selected", ""),
                    "arguments_passed": t["arguments"],
                    "python_executed": edu.get("python_action", ""),
                    "result_returned": t["result"],
                    "duration_ms": t["duration_ms"],
                    "status": t["status"],
                }
            )

        return {
            "user_requested": f'You asked: "{user_message}"',
            "gemini_understood": (
                f"Gemini ({model_name}) parsed your natural-language goal and recognized that {len(tool_executions)} "
                f"backend tool call(s) ({' → '.join(tool_names)}) were required to gather real data or perform actions."
            ),
            "tools_selected_why": (
                "Instead of guessing, the AI Agent selected structured function declarations matching your intent, "
                "generated JSON arguments, and waited for Python to execute them."
            ),
            "steps": steps_breakdown,
            "how_final_answer_generated": (
                "After Python executed each function and returned the structured JSON output via `Part.from_function_response`, "
                "Gemini read the real execution results and synthesized them into the final human-friendly reply."
            ),
        }

    def _build_error_response(
        self,
        *,
        request_id: str,
        user_message: str,
        model_name: str,
        error_detail: str,
        tool_executions: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        pending_confirmations: List[Dict[str, Any]],
        start_time: float,
    ) -> Dict[str, Any]:
        duration_ms = round((time.perf_counter() - start_time) * 1000)
        learning_data = self._build_learning_summary(
            user_message=user_message,
            model_name=model_name,
            tool_executions=tool_executions,
            final_answer=error_detail,
            error=error_detail,
        )
        activity_entry = storage.record_activity(
            {
                "id": request_id,
                "user_request": user_message,
                "status": "error",
                "model": model_name,
                "tools_used": [t["tool_name"] for t in tool_executions],
                "timeline": timeline,
                "final_response": error_detail,
                "duration_ms": duration_ms,
            }
        )
        return {
            "request_id": request_id,
            "success": False,
            "error": error_detail,
            "response": f"⚠️ **Agent Error**\n\n{error_detail}",
            "model": model_name,
            "tool_calls": tool_executions,
            "timeline": timeline,
            "pending_confirmations": pending_confirmations,
            "learning_mode": learning_data,
            "activity": activity_entry,
            "duration_ms": duration_ms,
        }


agent_instance = TaskPilotAgent()
