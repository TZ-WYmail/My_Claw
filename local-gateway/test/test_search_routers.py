from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import fulltext_search, search


def _empty_search_result() -> dict:
    return {
        "status": "success",
        "results": {
            "files": {"items": [], "total": 0},
            "tasks": {"items": [], "total": 0},
            "notes": {"items": [], "total": 0},
            "habits": {"items": [], "total": 0},
        },
        "total": 0,
        "scope": "all",
        "files": [],
        "tasks": [],
        "notes": [],
        "habits": [],
    }


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(search.router, prefix="/api")
    app.include_router(fulltext_search.router, prefix="/api")
    return TestClient(app)


def test_unified_search_router_uses_ai_tool():
    client = _build_client()

    with patch(
        "routers.search.execute_local_unified_search",
        new=AsyncMock(return_value=_empty_search_result()),
    ) as mocked:
        response = client.post(
            "/api/search",
            json={"keyword": "周报", "scope": "all", "category": "all", "page": 1, "page_size": 20},
        )

    assert response.status_code == 200
    mocked.assert_awaited_once()



def test_fulltext_router_uses_fulltext_service():
    client = _build_client()

    with patch(
        "routers.fulltext_search.search_fulltext",
        new=AsyncMock(return_value={"status": "success", "results": [], "total_results": 0}),
    ) as mocked:
        response = client.get("/api/search/fulltext", params={"q": "project", "top_k": 5})

    assert response.status_code == 200
    mocked.assert_awaited_once_with("project", None, 5)


def test_fulltext_index_stats_router_uses_fulltext_service():
    client = _build_client()

    with patch(
        "routers.fulltext_search.get_index_stats",
        new=AsyncMock(return_value={"status": "success", "indexed_files": 12}),
    ) as mocked:
        response = client.get("/api/search/index/stats")

    assert response.status_code == 200
    assert response.json()["indexed_files"] == 12
    mocked.assert_awaited_once_with()
