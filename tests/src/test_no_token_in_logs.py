import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def _log_calls_reading_a_token() -> list[str]:
    found = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in LOG_METHODS
            ):
                continue
            if any(isinstance(n, ast.Attribute) and n.attr == "TOKEN" for n in ast.walk(node)):
                found.append(f"{path.relative_to(SRC.parent)}:{node.lineno}")
    return found


def test_log_calls_do_not_include_a_token():
    assert _log_calls_reading_a_token() == []
