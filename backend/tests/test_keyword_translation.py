import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.search.translation import (
    GOOGLE_TRANSLATION_MODEL,
    GOOGLE_TRANSLATION_PROVIDER,
    KeywordTranslationResult,
    TranslationQuotaExceeded,
    _consume_translation_quota,
    translate_keyword_for_country,
)


def test_translate_keyword_uses_cache_before_quota_or_api(monkeypatch) -> None:
    cached_row = SimpleNamespace(translated_keyword="صمام صناعي")
    consume_quota = AsyncMock()
    request_translation = AsyncMock()

    monkeypatch.setattr(
        "app.services.search.translation._load_cached_translation",
        AsyncMock(return_value=cached_row),
    )
    monkeypatch.setattr(
        "app.services.search.translation.get_settings",
        lambda: SimpleNamespace(google_translate_api_key="google-test-key"),
    )
    monkeypatch.setattr("app.services.search.translation._consume_translation_quota", consume_quota)
    monkeypatch.setattr("app.services.search.translation._request_google_translation", request_translation)

    result = asyncio.run(translate_keyword_for_country(keyword="industrial valve", country="Egypt", user_id=None))

    assert result.status == "cached"
    assert result.translated_keyword == "صمام صناعي"
    consume_quota.assert_not_awaited()
    request_translation.assert_not_awaited()


def test_translate_keyword_returns_disabled_status_without_google_api_key(monkeypatch) -> None:
    consume_quota = AsyncMock()

    monkeypatch.setattr(
        "app.services.search.translation._load_cached_translation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.search.translation.get_settings",
        lambda: SimpleNamespace(google_translate_api_key=""),
    )
    monkeypatch.setattr("app.services.search.translation._consume_translation_quota", consume_quota)

    result = asyncio.run(translate_keyword_for_country(keyword="industrial valve", country="Egypt", user_id=None))

    assert result.status == "disabled_no_api_key"
    assert result.source == "system_config"
    consume_quota.assert_not_awaited()


def test_translate_keyword_reports_quota_exhausted_without_request(monkeypatch) -> None:
    request_translation = AsyncMock()

    monkeypatch.setattr(
        "app.services.search.translation._load_cached_translation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.search.translation.get_settings",
        lambda: SimpleNamespace(google_translate_api_key="google-test-key"),
    )
    monkeypatch.setattr(
        "app.services.search.translation._consume_translation_quota",
        AsyncMock(side_effect=TranslationQuotaExceeded("Daily translation limit reached")),
    )
    monkeypatch.setattr("app.services.search.translation._request_google_translation", request_translation)

    result = asyncio.run(translate_keyword_for_country(keyword="industrial valve", country="Egypt", user_id=None))

    assert result.status == "quota_exhausted"
    assert result.source == "quota"
    request_translation.assert_not_awaited()


def test_translate_keyword_success_returns_translated_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.search.translation._load_cached_translation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.search.translation.get_settings",
        lambda: SimpleNamespace(google_translate_api_key="google-test-key"),
    )
    monkeypatch.setattr("app.services.search.translation._consume_translation_quota", AsyncMock())
    monkeypatch.setattr(
        "app.services.search.translation._request_google_translation",
        AsyncMock(return_value="صمام صناعي"),
    )
    monkeypatch.setattr(
        "app.services.search.translation._save_translation",
        AsyncMock(return_value=SimpleNamespace(translated_keyword="صمام صناعي")),
    )

    result = asyncio.run(translate_keyword_for_country(keyword="industrial valve", country="Egypt", user_id=None))

    assert isinstance(result, KeywordTranslationResult)
    assert result.status == "translated"
    assert result.translated_keyword == "صمام صناعي"
    assert result.source == GOOGLE_TRANSLATION_PROVIDER


def test_translate_keyword_uses_same_as_input_status_when_google_translation_matches_keyword(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.search.translation._load_cached_translation",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.search.translation.get_settings",
        lambda: SimpleNamespace(google_translate_api_key="google-test-key"),
    )
    monkeypatch.setattr("app.services.search.translation._consume_translation_quota", AsyncMock())
    monkeypatch.setattr(
        "app.services.search.translation._request_google_translation",
        AsyncMock(return_value="industrial valve"),
    )
    monkeypatch.setattr(
        "app.services.search.translation._save_translation",
        AsyncMock(return_value=SimpleNamespace(translated_keyword="industrial valve")),
    )

    result = asyncio.run(translate_keyword_for_country(keyword="industrial valve", country="Egypt", user_id=None))

    assert result.status == "not_needed"
    assert result.source == "same_as_input"


def test_google_translation_request_writes_provider_and_model_to_quota_log(monkeypatch) -> None:
    created = []
    user_id = uuid.uuid4()

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _query):
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=user_id, role="admin"))

        def add(self, row):
            created.append(row)

        async def commit(self):
            return None

    monkeypatch.setattr("app.services.search.translation.SessionLocal", lambda: DummySession())

    asyncio.run(
        _consume_translation_quota(
            user_id=user_id,
            keyword="industrial valve",
            country_code="EG",
            target_language="ar",
        )
    )

    assert len(created) == 1
    assert created[0].provider == GOOGLE_TRANSLATION_PROVIDER
    assert created[0].model == GOOGLE_TRANSLATION_MODEL
