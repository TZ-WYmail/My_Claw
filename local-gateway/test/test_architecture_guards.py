import ast
from pathlib import Path

from routers import fulltext_search, search


REPO_ROOT = Path(__file__).resolve().parents[1]
INTERNAL_SOURCE_DIRS = ("application", "routers", "services")
BACKEND_SOURCE_DIRS = ("application", "routers", "services")
TASK_SERVICE_COMPAT_FILE = REPO_ROOT / "services" / "task_service.py"
MAIL_SERVICE_COMPAT_FILE = REPO_ROOT / "services" / "mail_service.py"
MAIL_SERVICE_RUNTIME_COMPAT_FILE = REPO_ROOT / "services" / "mail" / "compat.py"
MAIL_SERVICE_RUNTIME_ENV_FILE = REPO_ROOT / "services" / "mail" / "runtime_env.py"
MAIL_SOURCE_DIR = REPO_ROOT / "services" / "mail"
ADVANCED_ACTIONS_COMPAT_FILE = REPO_ROOT / "application" / "advanced_actions.py"
AI_TOOLS_COMPAT_FILE = REPO_ROOT / "application" / "ai_tools.py"
ADVANCED_COMPAT_ROUTER_FILE = REPO_ROOT / "routers" / "advanced_features.py"
FRONTEND_SOURCE_DIR = REPO_ROOT / "frontend" / "src"
TEST_SOURCE_DIR = REPO_ROOT / "test"
ADVANCED_COMPAT_PATH = "/api/" "advanced/"
SEARCH_LEGACY_PATH = "/api/search/" "legacy"
LOCAL_FILE_SEARCH_COMPAT_NAME = "local_file_search"
MAIN_ENTRY_FILE = REPO_ROOT / "main.py"
THIS_TEST_FILE = Path(__file__).resolve()
TASK_SERVICE_COMPAT_TEST_FILE = REPO_ROOT / "test" / "test_services.py"
ADVANCED_ACTIONS_COMPAT_TEST_FILE = REPO_ROOT / "test" / "test_advanced_application.py"


def _iter_internal_python_files():
    for dirname in INTERNAL_SOURCE_DIRS:
        for path in (REPO_ROOT / dirname).rglob("*.py"):
            if path in {
                TASK_SERVICE_COMPAT_FILE,
                MAIL_SERVICE_COMPAT_FILE,
                MAIL_SERVICE_RUNTIME_COMPAT_FILE,
                MAIL_SERVICE_RUNTIME_ENV_FILE,
                ADVANCED_ACTIONS_COMPAT_FILE,
                AI_TOOLS_COMPAT_FILE,
                THIS_TEST_FILE,
            }:
                continue
            yield path
    if MAIN_ENTRY_FILE.exists():
        yield MAIN_ENTRY_FILE


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


def _find_mail_service_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "services.mail_service":
                    findings.append(f"import services.mail_service (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "services.mail_service":
                findings.append(f"from services.mail_service import ... (line {node.lineno})")
            elif node.module == "services" and any(alias.name == "mail_service" for alias in node.names):
                findings.append(f"from services import mail_service (line {node.lineno})")

    return findings


def _find_advanced_actions_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "application.advanced_actions":
                    findings.append(f"import application.advanced_actions (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "application.advanced_actions":
                findings.append(f"from application.advanced_actions import ... (line {node.lineno})")
            elif node.module == "application" and any(alias.name == "advanced_actions" for alias in node.names):
                findings.append(f"from application import advanced_actions (line {node.lineno})")

    return findings


def _find_local_file_search_mentions(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    findings: list[str] = []

    for lineno, line in enumerate(content.splitlines(), start=1):
        if LOCAL_FILE_SEARCH_COMPAT_NAME in line:
            findings.append(f"local_file_search literal (line {lineno})")

    return findings


def _find_mail_compat_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "services.mail.compat":
                    findings.append(f"import services.mail.compat (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "services.mail.compat":
                findings.append(f"from services.mail.compat import ... (line {node.lineno})")
            elif node.module == "services.mail" and any(alias.name == "compat" for alias in node.names):
                findings.append(f"from services.mail import compat (line {node.lineno})")

    return findings


def test_internal_code_no_longer_imports_task_service_directly():
    findings: dict[str, list[str]] = {}

    for path in _iter_internal_python_files():
        path_findings = _find_task_service_imports(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_internal_code_no_longer_imports_mail_service_directly():
    findings: dict[str, list[str]] = {}

    for path in _iter_internal_python_files():
        path_findings = _find_mail_service_imports(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_internal_code_no_longer_imports_advanced_actions_directly():
    findings: dict[str, list[str]] = {}

    for path in _iter_internal_python_files():
        path_findings = _find_advanced_actions_imports(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_internal_code_no_longer_uses_local_file_search_name():
    findings: dict[str, list[str]] = {}

    for path in _iter_internal_python_files():
        path_findings = _find_local_file_search_mentions(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_internal_code_no_longer_imports_mail_compat_directly():
    findings: dict[str, list[str]] = {}

    for path in _iter_internal_python_files():
        path_findings = _find_mail_compat_imports(path)
        if path_findings:
            findings[str(path.relative_to(REPO_ROOT))] = path_findings

    assert findings == {}


def test_mail_submodules_no_longer_reference_removed_compat_module():
    findings: list[str] = []

    for path in MAIL_SOURCE_DIR.rglob("*.py"):
        if path in {MAIL_SERVICE_RUNTIME_ENV_FILE,}:
            continue
        content = path.read_text(encoding="utf-8")
        if "services.mail.compat" in content:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_advanced_compat_router_has_been_removed():
    assert not ADVANCED_COMPAT_ROUTER_FILE.exists()


def test_backend_sources_no_longer_reference_advanced_compat_router():
    findings: list[str] = []

    for dirname in BACKEND_SOURCE_DIRS:
        for path in (REPO_ROOT / dirname).rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            if "advanced_features" in content or ADVANCED_COMPAT_PATH in content:
                findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_search_router_ownership_boundaries_are_stable():
    assert sorted(route.path for route in search.router.routes) == ["/search"]
    assert sorted(route.path for route in fulltext_search.router.routes) == [
        "/search/fulltext",
        "/search/index",
        "/search/index/rebuild",
        "/search/index/stats",
    ]


def test_frontend_sources_no_longer_use_advanced_compat_paths():
    findings: list[str] = []

    for path in FRONTEND_SOURCE_DIR.rglob("*.[jt]sx"):
        content = path.read_text(encoding="utf-8")
        if ADVANCED_COMPAT_PATH in content:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_tests_no_longer_use_advanced_compat_paths():
    findings: list[str] = []

    for path in TEST_SOURCE_DIR.rglob("test_*.py"):
        if path == THIS_TEST_FILE:
            continue
        content = path.read_text(encoding="utf-8")
        if ADVANCED_COMPAT_PATH in content:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_tests_no_longer_use_legacy_search_path():
    findings: list[str] = []

    for path in TEST_SOURCE_DIR.rglob("test_*.py"):
        if path == THIS_TEST_FILE:
            continue
        content = path.read_text(encoding="utf-8")
        if SEARCH_LEGACY_PATH in content:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_task_service_init_db_is_only_covered_by_compat_test():
    findings: list[str] = []

    for path in TEST_SOURCE_DIR.rglob("test_*.py"):
        if path == THIS_TEST_FILE:
            continue
        content = path.read_text(encoding="utf-8")
        if "task_service.init_db(" not in content:
            continue
        if path != TASK_SERVICE_COMPAT_TEST_FILE:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []


def test_advanced_actions_is_only_used_by_compat_test():
    findings: list[str] = []

    for path in TEST_SOURCE_DIR.rglob("test_*.py"):
        content = path.read_text(encoding="utf-8")
        if "advanced_actions" not in content:
            continue
        if path not in {ADVANCED_ACTIONS_COMPAT_TEST_FILE, THIS_TEST_FILE}:
            findings.append(str(path.relative_to(REPO_ROOT)))

    assert findings == []
