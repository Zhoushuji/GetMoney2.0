from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import SessionLocal
from app.models.keyword_translation import KeywordTranslation
from app.models.translation_api_request import TranslationApiRequest
from app.models.user import User
from app.services.extraction.country_detection import resolve_country
from app.services.search.keyword_cache import SEARCH_STRATEGY_VERSION, normalize_keyword, secondary_official_language

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
GOOGLE_TRANSLATION_PROVIDER = "google"
GOOGLE_TRANSLATION_MODEL = "google-translate-basic-v2"
SOURCE_LANGUAGE = "en"


class TranslationError(Exception):
    pass


class TranslationQuotaExceeded(TranslationError):
    pass


@dataclass(frozen=True)
class KeywordTranslationResult:
    country: str
    country_code: str
    target_language: str | None
    translated_keyword: str | None
    status: str
    source: str
    error: str | None = None

    @property
    def should_search(self) -> bool:
        return self.status in {"cached", "translated"} and bool(self.translated_keyword) and bool(self.target_language)

    def as_dict(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "country_code": self.country_code,
            "target_language": self.target_language,
            "translated_keyword": self.translated_keyword,
            "status": self.status,
            "source": self.source,
            "error": self.error,
        }


def _start_of_today_utc() -> datetime:
    local_now = datetime.now().astimezone()
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_start.astimezone(timezone.utc)


def _sanitize_translation(value: str | None) -> str | None:
    text = " ".join(unescape(str(value or "")).strip().split())
    if not text:
        return None
    return text.strip("\"' ")


async def _consume_translation_quota(
    *,
    user_id: UUID | None,
    keyword: str,
    country_code: str,
    target_language: str,
) -> None:
    if user_id is None:
        return
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id).with_for_update())
        user = result.scalar_one_or_none()
        if user is None:
            raise TranslationError("User not found for translation quota")
        if user.role != "admin":
            requests_today = int(
                (
                    await session.execute(
                        select(func.count(TranslationApiRequest.id)).where(
                            TranslationApiRequest.user_id == user.id,
                            TranslationApiRequest.created_at >= _start_of_today_utc(),
                        )
                    )
                ).scalar_one()
                or 0
            )
            if requests_today >= user.daily_translation_limit:
                raise TranslationQuotaExceeded("Daily translation limit reached")
        session.add(
            TranslationApiRequest(
                user_id=user.id,
                provider=GOOGLE_TRANSLATION_PROVIDER,
                keyword=keyword,
                country_code=country_code,
                source_language=SOURCE_LANGUAGE,
                target_language=target_language,
                model=GOOGLE_TRANSLATION_MODEL,
            )
        )
        await session.commit()


async def _load_cached_translation(
    *,
    keyword_normalized: str,
    country_code: str,
    target_language: str,
) -> KeywordTranslation | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(KeywordTranslation).where(
                KeywordTranslation.keyword_normalized == keyword_normalized,
                KeywordTranslation.country_code == country_code,
                KeywordTranslation.source_language == SOURCE_LANGUAGE,
                KeywordTranslation.target_language == target_language,
                KeywordTranslation.provider == GOOGLE_TRANSLATION_PROVIDER,
                KeywordTranslation.model == GOOGLE_TRANSLATION_MODEL,
                KeywordTranslation.strategy_version == SEARCH_STRATEGY_VERSION,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.last_requested_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        return row


async def _save_translation(
    *,
    keyword: str,
    keyword_normalized: str,
    country_code: str,
    target_language: str,
    translated_keyword: str,
) -> KeywordTranslation:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result = await session.execute(
            select(KeywordTranslation).where(
                KeywordTranslation.keyword_normalized == keyword_normalized,
                KeywordTranslation.country_code == country_code,
                KeywordTranslation.source_language == SOURCE_LANGUAGE,
                KeywordTranslation.target_language == target_language,
                KeywordTranslation.provider == GOOGLE_TRANSLATION_PROVIDER,
                KeywordTranslation.model == GOOGLE_TRANSLATION_MODEL,
                KeywordTranslation.strategy_version == SEARCH_STRATEGY_VERSION,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = KeywordTranslation(
                keyword=keyword,
                keyword_normalized=keyword_normalized,
                country_code=country_code,
                source_language=SOURCE_LANGUAGE,
                target_language=target_language,
                translated_keyword=translated_keyword,
                provider=GOOGLE_TRANSLATION_PROVIDER,
                model=GOOGLE_TRANSLATION_MODEL,
                strategy_version=SEARCH_STRATEGY_VERSION,
                last_requested_at=now,
            )
            session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                result = await session.execute(
                    select(KeywordTranslation).where(
                        KeywordTranslation.keyword_normalized == keyword_normalized,
                        KeywordTranslation.country_code == country_code,
                        KeywordTranslation.source_language == SOURCE_LANGUAGE,
                        KeywordTranslation.target_language == target_language,
                        KeywordTranslation.provider == GOOGLE_TRANSLATION_PROVIDER,
                        KeywordTranslation.model == GOOGLE_TRANSLATION_MODEL,
                        KeywordTranslation.strategy_version == SEARCH_STRATEGY_VERSION,
                    )
                )
                row = result.scalar_one()
                row.translated_keyword = translated_keyword
                row.last_requested_at = now
                await session.commit()
        else:
            row.keyword = keyword
            row.translated_keyword = translated_keyword
            row.last_requested_at = now
            await session.commit()
        await session.refresh(row)
        return row


async def _request_google_translation(*, api_key: str, keyword: str, target_language: str) -> str:
    payload = {
        "q": keyword,
        "source": SOURCE_LANGUAGE,
        "target": target_language,
        "format": "text",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GOOGLE_TRANSLATE_URL,
            params={"key": api_key},
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        body = response.json()
    translations = (((body.get("data") or {}).get("translations")) or [])
    translated = _sanitize_translation(translations[0].get("translatedText") if translations else None)
    if not translated:
        raise TranslationError("Google translation response did not contain text")
    return translated


async def translate_keyword_for_country(
    *,
    keyword: str,
    country: str,
    user_id: UUID | None,
) -> KeywordTranslationResult:
    resolved = resolve_country(country)
    country_code = resolved.code if resolved is not None else str(country or "").strip().upper()
    target_language = secondary_official_language(country)
    country_name = resolved.name_en if resolved is not None else str(country or "").strip()
    if not target_language:
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=None,
            translated_keyword=None,
            status="not_needed",
            source="primary_search_only",
        )

    keyword_normalized = normalize_keyword(keyword)
    cached = await _load_cached_translation(
        keyword_normalized=keyword_normalized,
        country_code=country_code,
        target_language=target_language,
    )
    if cached is not None:
        if normalize_keyword(cached.translated_keyword) == keyword_normalized:
            return KeywordTranslationResult(
                country=country_name,
                country_code=country_code,
                target_language=target_language,
                translated_keyword=cached.translated_keyword,
                status="not_needed",
                source="same_as_input_cache",
            )
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=cached.translated_keyword,
            status="cached",
            source="google_cache",
        )

    api_key = get_settings().google_translate_api_key.strip()
    if not api_key:
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=None,
            status="disabled_no_api_key",
            source="system_config",
        )

    try:
        await _consume_translation_quota(
            user_id=user_id,
            keyword=keyword,
            country_code=country_code,
            target_language=target_language,
        )
        translated_keyword = await _request_google_translation(
            api_key=api_key,
            keyword=keyword,
            target_language=target_language,
        )
        cache_row = await _save_translation(
            keyword=keyword,
            keyword_normalized=keyword_normalized,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=translated_keyword,
        )
        if normalize_keyword(cache_row.translated_keyword) == keyword_normalized:
            return KeywordTranslationResult(
                country=country_name,
                country_code=country_code,
                target_language=target_language,
                translated_keyword=cache_row.translated_keyword,
                status="not_needed",
                source="same_as_input",
            )
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=cache_row.translated_keyword,
            status="translated",
            source=GOOGLE_TRANSLATION_PROVIDER,
        )
    except TranslationQuotaExceeded as exc:
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=None,
            status="quota_exhausted",
            source="quota",
            error=str(exc),
        )
    except Exception as exc:
        return KeywordTranslationResult(
            country=country_name,
            country_code=country_code,
            target_language=target_language,
            translated_keyword=None,
            status="failed",
            source=GOOGLE_TRANSLATION_PROVIDER,
            error=str(exc),
        )
