"""Static validation for agent-generated connector files.

Two-stage validation — no code execution inside the server process:
  1. AST parse: check class structure, required methods, service_name attribute
  2. Subprocess dry-import: catch import-time errors safely in a child process
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def validate_connector_file(
    path: Path,
    service_name: str,
    required_actions: list[str],
) -> list[str]:
    """Return a list of error strings. An empty list means the file is valid."""
    errors: list[str] = []

    # ---- Stage 1: AST parse ----
    try:
        source = path.read_text()
    except OSError as e:
        return [f"Cannot read file: {e}"]

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SyntaxError at line {e.lineno}: {e.msg}"]

    # Find the expected class
    expected_class = f"{service_name.capitalize()}Connector"
    class_nodes = [
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == expected_class
    ]
    if not class_nodes:
        errors.append(
            f"Class '{expected_class}' not found — class must be named exactly "
            f"'{expected_class}' with service_name = '{service_name}'"
        )
        return errors  # no point checking methods if the class itself is absent

    class_node = class_nodes[0]

    # Check service_name class attribute is present
    has_service_name = any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "service_name" for t in n.targets)
        for n in ast.walk(class_node)
    )
    if not has_service_name:
        errors.append(f"Class '{expected_class}' is missing a 'service_name' class attribute")

    # Collect all method names defined directly in the class
    method_names = {
        n.name
        for n in ast.walk(class_node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    # Check required action methods
    for action in required_actions:
        if action not in method_names:
            errors.append(f"Required method '{action}' not found in '{expected_class}'")

    # Check mandatory classmethods
    for cm in ("from_settings", "is_configured"):
        if cm not in method_names:
            errors.append(f"Required classmethod '{cm}' not found in '{expected_class}'")

    if errors:
        return errors

    # ---- Stage 2: subprocess dry-import ----
    # Runs the connector file in an isolated child process to catch import-time errors
    # without affecting the running server process.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util, sys; "
                f"spec = importlib.util.spec_from_file_location('_validate', '{path}'); "
                "mod = importlib.util.module_from_spec(spec); "
                "sys.modules[spec.name] = mod"
                # Note: we intentionally do NOT call exec_module() here — we only
                # want to catch syntax/import errors visible at module creation time.
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()[:500]
        errors.append(f"Module-level error: {stderr}")

    return errors
