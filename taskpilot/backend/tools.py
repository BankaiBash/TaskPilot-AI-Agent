"""Safe, validated tools for the TaskPilot AI Agent."""

from __future__ import annotations

import ast
import math
import operator
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from google.genai import types

import storage

# Allowed binary and unary operators for the AST-based safe calculator
_SAFE_BIN_OPS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARY_OPS: Dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SAFE_MATH_FUNCS: Dict[str, Callable[..., Any]] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
    "pow": math.pow,
}

_SAFE_CONSTANTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

MAX_EXPONENT = 1000
MAX_EXPRESSION_LENGTH = 300


def _eval_ast_node(node: ast.AST) -> float | int:
    """Recursively evaluate a validated AST node without using eval()."""
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ValueError(f"Unknown identifier '{node.id}'. Allowed constants: {', '.join(_SAFE_CONSTANTS)}")

    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_eval_ast_node(node.operand))

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BIN_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT:
                raise ValueError(f"Exponent {right} exceeds safety limit ({MAX_EXPONENT}).")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ZeroDivisionError("Division by zero is undefined.")
        return op_func(left, right)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_MATH_FUNCS:
            func_name = getattr(node.func, "id", "unknown")
            raise ValueError(
                f"Disallowed function '{func_name}'. Allowed functions: {', '.join(sorted(_SAFE_MATH_FUNCS))}"
            )
        if node.keywords:
            raise ValueError("Keyword arguments are not permitted in calculator expressions.")
        args = [_eval_ast_node(arg) for arg in node.args]
        return _SAFE_MATH_FUNCS[node.func.id](*args)

    raise ValueError(f"Disallowed syntax element in expression: {type(node).__name__}")


def calculator(expression: str) -> Dict[str, Any]:
    """Evaluate a mathematical expression safely using an AST parser.

    Args:
        expression: A mathematical expression string such as '(245 * 18) + sqrt(144)' or '15% of 480'.
    """
    if not isinstance(expression, str) or not expression.strip():
        return {
            "success": False,
            "error": "Expression must be a non-empty string.",
        }

    raw_expr = expression.strip()
    if len(raw_expr) > MAX_EXPRESSION_LENGTH:
        return {
            "success": False,
            "error": f"Expression exceeds maximum length of {MAX_EXPRESSION_LENGTH} characters.",
        }

    # Normalize common natural math notations (e.g., '^' -> '**', '×' -> '*', '÷' -> '/')
    normalized = (
        raw_expr.replace("^", "**")
        .replace("×", "*")
        .replace("÷", "/")
    )

    try:
        parsed = ast.parse(normalized, mode="eval")
        result = _eval_ast_node(parsed)
        if isinstance(result, float):
            if math.isnan(result) or math.isinf(result):
                return {
                    "success": False,
                    "expression": raw_expr,
                    "error": "Calculation resulted in an non-finite value (NaN or Infinity).",
                }
            # Clean floating point representation if close to integer or round to 8 decimals
            formatted_result: int | float = int(result) if result.is_integer() else round(result, 8)
        else:
            formatted_result = result

        return {
            "success": True,
            "expression": raw_expr,
            "normalized_expression": normalized,
            "result": formatted_result,
        }
    except ZeroDivisionError as exc:
        return {
            "success": False,
            "expression": raw_expr,
            "error": str(exc),
        }
    except (SyntaxError, ValueError, TypeError, OverflowError) as exc:
        return {
            "success": False,
            "expression": raw_expr,
            "error": f"Invalid mathematical expression: {exc}",
        }


def add_task(name: str, deadline: str = "No deadline specified") -> Dict[str, Any]:
    """Create and persist a new task with a name and deadline.

    Args:
        name: The title or description of the task to save.
        deadline: The target due date or time (e.g., '2026-11-05 17:00' or 'Tomorrow at 5 PM').
    """
    if not isinstance(name, str) or not name.strip():
        return {
            "success": False,
            "error": "Task name is required and must be a non-empty string.",
        }
    if len(name.strip()) > 200:
        return {
            "success": False,
            "error": "Task name cannot exceed 200 characters.",
        }
    clean_deadline = deadline.strip() if isinstance(deadline, str) and deadline.strip() else "No deadline specified"
    if len(clean_deadline) > 100:
        return {
            "success": False,
            "error": "Deadline cannot exceed 100 characters.",
        }

    try:
        created = storage.create_task(name=name.strip(), deadline=clean_deadline)
        return {
            "success": True,
            "message": f"Task '{created['name']}' created with ID {created['id']}.",
            "task": created,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to store task: {exc}",
        }


def view_tasks(status: str = "all") -> Dict[str, Any]:
    """Retrieve saved tasks from persistent storage, optionally filtered by completion status.

    Args:
        status: Filter tasks by completion status. Allowed values: 'all', 'active', 'completed'.
    """
    allowed_statuses = {"all", "active", "completed", "pending", "done", "incomplete"}
    clean_status = (status or "all").strip().lower()
    if clean_status not in allowed_statuses:
        return {
            "success": False,
            "error": f"Invalid status filter '{status}'. Use 'all', 'active', or 'completed'.",
        }

    tasks = storage.load_tasks(status_filter=clean_status)
    all_tasks = storage.load_tasks(status_filter="all")
    active_count = sum(1 for t in all_tasks if not t.get("completed"))
    completed_count = sum(1 for t in all_tasks if t.get("completed"))

    return {
        "success": True,
        "filter": clean_status,
        "count": len(tasks),
        "total_active": active_count,
        "total_completed": completed_count,
        "tasks": tasks,
    }


def delete_task(task_id: str, confirmed: bool = False) -> Dict[str, Any]:
    """Delete a task by its unique ID. Destructive operation requiring human confirmation.

    Args:
        task_id: The unique identifier of the task (e.g., 'TSK-1001').
        confirmed: Whether the human user has explicitly confirmed deletion.
    """
    if not isinstance(task_id, str) or not task_id.strip():
        return {
            "success": False,
            "error": "A valid non-empty task_id is required.",
        }

    clean_id = task_id.strip().upper()
    existing = storage.get_task(clean_id)
    if not existing:
        return {
            "success": False,
            "task_id": clean_id,
            "error": f"Task '{clean_id}' was not found. Use view_tasks first to inspect valid task IDs.",
        }

    if not confirmed:
        return {
            "success": False,
            "requires_confirmation": True,
            "status": "awaiting_human_confirmation",
            "task": existing,
            "message": (
                f"Deletion of task '{existing['name']}' (ID: {existing['id']}) is paused pending "
                "explicit human approval. Please ask the user to confirm deletion."
            ),
        }

    deleted = storage.remove_task(clean_id)
    if not deleted:
        return {
            "success": False,
            "task_id": clean_id,
            "error": f"Failed to delete task '{clean_id}'.",
        }

    return {
        "success": True,
        "deleted_task": deleted,
        "message": f"Task '{deleted['name']}' (ID: {deleted['id']}) was permanently deleted.",
    }


def get_current_datetime() -> Dict[str, Any]:
    """Retrieve the current system date, time, weekday, and local timezone."""
    now = datetime.now().astimezone()
    return {
        "success": True,
        "iso": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "readable": now.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
        "weekday": now.strftime("%A"),
        "timezone": str(now.tzinfo),
    }


# Gemini Function Declarations for official google-genai tool calling
GEMINI_TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="calculator",
            description=(
                "Perform accurate mathematical calculations safely. Use this whenever the user asks "
                "to compute arithmetic, percentages, powers, square roots, or multi-step math formulas."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "expression": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "Valid mathematical expression to evaluate, e.g. '(1250 * 1.18) - 150' "
                            "or 'sqrt(256) + 42'. Allowed functions: sqrt, sin, cos, tan, log, log10, exp, abs, round, ceil, floor, min, max, pow."
                        ),
                    ),
                },
                required=["expression"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_task",
            description=(
                "Create and store a new task with a name and deadline in persistent storage. "
                "If the user mentions a relative deadline like 'tomorrow' or 'in 3 days', call "
                "get_current_datetime first so you can record a concrete deadline."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "name": types.Schema(
                        type=types.Type.STRING,
                        description="Clear, concise title of the task.",
                    ),
                    "deadline": types.Schema(
                        type=types.Type.STRING,
                        description="Deadline date/time string (e.g., '2026-11-05 17:00' or 'Nov 6, 2026 5:00 PM').",
                    ),
                },
                required=["name", "deadline"],
            ),
        ),
        types.FunctionDeclaration(
            name="view_tasks",
            description=(
                "Retrieve saved tasks from storage. Can fetch all tasks, only active (incomplete) tasks, "
                "or only completed tasks."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "status": types.Schema(
                        type=types.Type.STRING,
                        description="Filter by completion status: 'all', 'active', or 'completed'. Defaults to 'all'.",
                        enum=["all", "active", "completed"],
                    ),
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="delete_task",
            description=(
                "Request deletion of a task by its unique ID (e.g., 'TSK-1001'). If you do not know the "
                "exact task ID, call view_tasks first to find it. Deletion requires human approval."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "task_id": types.Schema(
                        type=types.Type.STRING,
                        description="The unique ID of the task to delete (e.g. 'TSK-1002').",
                    ),
                },
                required=["task_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_current_datetime",
            description=(
                "Retrieve the current system date, time, day of the week, and timezone. "
                "Always call this when the user asks for the current time/date or specifies relative deadlines."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
                required=[],
            ),
        ),
    ]
)

# Educational explanations for Learning Mode
TOOL_EDUCATIONAL_META: Dict[str, Dict[str, str]] = {
    "calculator": {
        "title": "Calculator Tool",
        "why_selected": "Gemini detected a mathematical calculation that requires exact arithmetic rather than language model estimation.",
        "python_action": "Parsed the math expression into an Abstract Syntax Tree (AST) and evaluated allowed operators safely without eval().",
    },
    "add_task": {
        "title": "Add Task Tool",
        "why_selected": "Gemini identified an intent to create and persist a new task item with a name and target deadline.",
        "python_action": "Validated the task fields, assigned a unique ID, and wrote the updated task list atomically to data/tasks.json.",
    },
    "view_tasks": {
        "title": "View Tasks Tool",
        "why_selected": "Gemini needed to inspect the current tasks stored on disk to answer your query or look up task IDs.",
        "python_action": "Read data/tasks.json, applied the requested completion status filter, and returned the matching task records.",
    },
    "delete_task": {
        "title": "Delete Task Tool (Human-in-the-Loop)",
        "why_selected": "Gemini recognized a request to remove a specific task by its unique ID.",
        "python_action": "Checked human-approval state; destructive operations pause for user confirmation before removing data from data/tasks.json.",
    },
    "get_current_datetime": {
        "title": "Current Date & Time Tool",
        "why_selected": "LLMs do not have a built-in real-time clock, so Gemini invoked the system clock tool to get the exact current date and time.",
        "python_action": "Queried Python's datetime.now().astimezone() to return the real-time clock, weekday, and timezone.",
    },
}


def execute_tool(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    confirmed_delete_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """Dispatch and execute a named tool with strict input validation and error handling."""
    args = dict(arguments or {})

    if tool_name == "calculator":
        return calculator(expression=str(args.get("expression", "")))

    if tool_name == "add_task":
        return add_task(
            name=str(args.get("name", "")),
            deadline=str(args.get("deadline", "No deadline specified")),
        )

    if tool_name == "view_tasks":
        return view_tasks(status=str(args.get("status", "all")))

    if tool_name == "delete_task":
        task_id = str(args.get("task_id", "")).strip().upper()
        # Security guardrail: ignore any model-supplied 'confirmed' flag; only honor human-verified IDs
        is_confirmed = bool(confirmed_delete_ids and task_id in confirmed_delete_ids)
        return delete_task(task_id=task_id, confirmed=is_confirmed)

    if tool_name == "get_current_datetime":
        return get_current_datetime()

    return {
        "success": False,
        "error": f"Unknown tool '{tool_name}'. Available tools: calculator, add_task, view_tasks, delete_task, get_current_datetime.",
    }
