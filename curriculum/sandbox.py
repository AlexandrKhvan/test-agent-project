"""Small, defensive Python executor for learner-submitted code.

This module is a guardrail, not a replacement for OS/container isolation.  In
production it should run inside an unprivileged, resource-limited container.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any

_MAX_TIMEOUT_SECONDS = 5
_BLOCKED_MODULES = frozenset(
    {"os", "sys", "shutil", "socket", "subprocess", "pathlib", "ctypes", "signal", "multiprocessing"}
)
_BLOCKED_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)


def _result(success: bool, stdout: str = "", stderr: str = "", execution_time: float = 0.0) -> dict[str, Any]:
    """Create the stable result shape returned to the calling agent."""
    return {
        "success": success,
        "stdout": stdout,
        "stderr": stderr,
        "execution_time": round(execution_time, 6),
    }


class _SafetyVisitor(ast.NodeVisitor):
    """Reject syntax that enables file, process, network, or reflection access."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if alias.name.split(".", maxsplit=1)[0] in _BLOCKED_MODULES:
                self.errors.append(f"Import of '{alias.name}' is not allowed.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        if module.split(".", maxsplit=1)[0] in _BLOCKED_MODULES or node.level:
            self.errors.append(f"Import from '{module or 'relative module'}' is not allowed.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALLS:
            self.errors.append(f"Call to '{node.func.id}' is not allowed.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id == "__builtins__":
            self.errors.append("Access to '__builtins__' is not allowed.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.errors.append("Dunder attribute access is not allowed.")
        self.generic_visit(node)


def _validate_code(code: str) -> str | None:
    """Return an error description, or ``None`` when code passes AST checks."""
    try:
        tree = ast.parse(code, mode="exec")
    except (SyntaxError, ValueError, TypeError) as exc:
        return f"Invalid Python code: {exc}"

    visitor = _SafetyVisitor()
    visitor.visit(tree)
    return " ".join(dict.fromkeys(visitor.errors)) or None


def execute_code(code: str, timeout_seconds: int = 5) -> dict[str, Any]:
    """Execute safe learner code in a child Python process.

    The timeout can be shorter than five seconds but can never exceed the
    required hard five-second limit.  Failures, invalid input, and timeouts are
    represented in the returned dictionary rather than raised to the caller.
    """
    started_at = perf_counter()
    if not isinstance(code, str):
        return _result(False, stderr="Code must be a string.", execution_time=perf_counter() - started_at)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        return _result(False, stderr="timeout_seconds must be a positive integer.", execution_time=perf_counter() - started_at)

    validation_error = _validate_code(code)
    if validation_error:
        return _result(False, stderr=validation_error, execution_time=perf_counter() - started_at)

    timeout = min(timeout_seconds, _MAX_TIMEOUT_SECONDS)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as script:
            script.write(code)
            temporary_path = Path(script.name)

        completed = subprocess.run(
            [sys.executable, "-I", str(temporary_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=tempfile.gettempdir(),
            env={"PYTHONIOENCODING": "utf-8", "PATH": os.environ.get("PATH", "")},
        )
        return _result(
            completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
            execution_time=perf_counter() - started_at,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        message = f"Execution exceeded the {timeout}-second limit."
        return _result(False, stdout=stdout, stderr=f"{stderr}\n{message}".strip(), execution_time=perf_counter() - started_at)
    except (OSError, subprocess.SubprocessError) as exc:
        return _result(False, stderr=f"Unable to execute code: {exc}", execution_time=perf_counter() - started_at)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
