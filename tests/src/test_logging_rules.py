import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def _warnings_with_traceback() -> list[str]:
    found = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "warning"
                and any(kw.arg in ("exc_info", "stack_info") for kw in node.keywords)
            ):
                found.append(f"{path.relative_to(SRC.parent)}:{node.lineno}")
    return found


def test_warnings_do_not_log_a_traceback():
    assert _warnings_with_traceback() == []
