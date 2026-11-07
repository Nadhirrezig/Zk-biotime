"""The engine must stay pure Python: no Qt, no database driver."""
import ast
from pathlib import Path

ENGINE = Path(__file__).parent.parent / "src" / "zkreport" / "engine"
FORBIDDEN = ("PyQt6", "psycopg", "sqlite3", "keyring", "zkreport.db", "zkreport.ui", "zkreport.store")


def test_engine_has_no_forbidden_imports():
    for path in ENGINE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(FORBIDDEN), f"{path.name} imports {name}"
