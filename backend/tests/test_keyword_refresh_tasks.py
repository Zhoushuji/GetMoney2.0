import asyncio

from app.workers import keyword_refresh_tasks as worker_module


def test_refresh_due_keywords_loads_country_source_cache(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_load_country_search_source_cache() -> None:
        calls.append("load")

    async def fake_load_due_search_keywords(limit: int):
        calls.append(f"due:{limit}")
        return []

    monkeypatch.setattr(worker_module, "load_country_search_source_cache", fake_load_country_search_source_cache)
    monkeypatch.setattr(worker_module, "_load_due_search_keywords", fake_load_due_search_keywords)

    result = asyncio.run(worker_module._refresh_due_keywords(3))

    assert result == {"refreshed": 0, "skipped": 0}
    assert calls == ["load", "due:3"]
