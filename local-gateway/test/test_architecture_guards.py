import ast
from pathlib import Path

from routers import advanced_features, file_search, fulltext_search, search


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("application", "routers", "services", "test")
TASK_SERVICE_COMPAT_FILE = REPO_ROOT / "services" / "task_service.py"
THIS_TEST_FILE = Path(__file__).resolve()


def _iter_python_files():
    for dirname in SOURCE_DIRS:
        for path in (REPO_ROOT / dirname).rglob("*.py"):
            if path in {TASK_SERVICE_COMPAT_FILE, THIS_TEST_FILE}:
                continue
            yield path


def _find_task_service_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "services.task_service":
                    findings.append(f"import services.task_service (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "services.task_service":
                findings.append(f"from services.task_service import ... (line {node.lineno})")
            elif node.module == "services" and any(alias.name == "task_service" for alias in node.names):
                findings.append(f"from services import task_service (line {node.lineno})")

    return findings


def test_internal_code_no_longer_imports_task_service_directly():
    findings: dict[str, list[str]] = {}

    for path in _iter_python_files():
        path_findings = _find_task_service_imports(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_advanced_features_router_is_compatibility_alias_only():
    route_modules = {route.endpoint.__module__ for route in advanced_features.router.routes}

    assert route_modules == {
        "routers.tags",
        "routers.subtasks",
        "routers.pomodoro",
        "routers.calendar",
        "routers.task_detail",
    }
    assert "routers.advanced_features" not in route_modules


def test_search_router_ownership_boundaries_are_stable():
    assert sorted(route.path for route in search.router.routes) == ["/search"]
    assert sorted(route.path for route in file_search.router.routes) == ["/search/legacy"]
    assert sorted(route.path for route in fulltext_search.router.routes) == [
        "/search/fulltext",
        "/search/index",
        "/search/index/rebuild",
        "/search/index/stats",
    ]
