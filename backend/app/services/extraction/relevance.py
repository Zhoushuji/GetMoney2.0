from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

BLOCKED_DOMAIN_FAMILIES: dict[str, str] = {
    "ubuy": "retailer",
    "amazon": "marketplace",
    "jumia": "marketplace",
    "olx": "classifieds",
    "dubizzle": "classifieds",
}
MARKETPLACE_TERMS = (
    "marketplace",
    "shop now",
    "buy online",
    "cart",
    "e-commerce",
    "ecommerce",
    "online store",
    "shopping",
)
CLASSIFIEDS_TERMS = ("classifieds", "buy and sell", "for sale", "post ad", "ads")
MEDIA_TERMS = ("news", "magazine", "media", "blog", "press release", "article")
RETAIL_TERMS = ("retail", "consumer", "online shopping", "order now")


@dataclass(frozen=True)
class RelevanceResult:
    category: str
    evidence: tuple[str, ...]
    positive_hits: tuple[str, ...]
    negative_hits: tuple[str, ...]

    @property
    def is_relevant(self) -> bool:
        return self.category == "relevant"

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "evidence": list(self.evidence),
            "positive_hits": list(self.positive_hits),
            "negative_hits": list(self.negative_hits),
        }


class IndustryRelevanceClassifier:
    def classify(
        self,
        *,
        website: str,
        company_name: str | None,
        search_title: str | None,
        search_snippet: str | None,
        homepage_html: str | None,
    ) -> RelevanceResult:
        host = self._host(website)
        text = self._combined_text(company_name, search_title, search_snippet, homepage_html)
        for blocked, category in BLOCKED_DOMAIN_FAMILIES.items():
            if blocked in host:
                return RelevanceResult(
                    category=category,
                    evidence=(f"blocked_domain:{blocked}",),
                    positive_hits=(),
                    negative_hits=(blocked,),
                )
        category_signals = {
            "marketplace": self._find_terms(text, MARKETPLACE_TERMS),
            "classifieds": self._find_terms(text, CLASSIFIEDS_TERMS),
            "media": self._find_terms(text, MEDIA_TERMS),
            "retailer": self._find_terms(text, RETAIL_TERMS),
        }
        for category in ("marketplace", "classifieds", "media", "retailer"):
            if category_signals[category]:
                return RelevanceResult(
                    category=category,
                    evidence=tuple(f"{category}:{item}" for item in category_signals[category]),
                    positive_hits=(),
                    negative_hits=category_signals[category],
                )
        return RelevanceResult(
            category="relevant",
            evidence=("no_category_conflict",),
            positive_hits=(),
            negative_hits=(),
        )

    def _combined_text(
        self,
        company_name: str | None,
        search_title: str | None,
        search_snippet: str | None,
        homepage_html: str | None,
    ) -> str:
        soup_text = ""
        if homepage_html:
            soup_text = BeautifulSoup(homepage_html, "html.parser").get_text(" ", strip=True)
        return " ".join(
            part
            for part in [company_name or "", search_title or "", search_snippet or "", soup_text]
            if part
        ).lower()

    def _find_terms(self, text: str, terms: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        hits: list[str] = []
        for term in terms:
            normalized = " ".join(str(term or "").split()).strip().lower()
            if not normalized:
                continue
            pattern = re.escape(normalized)
            if re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text):
                hits.append(normalized)
        return tuple(hits)

    def _host(self, website: str) -> str:
        parsed = urlparse(website if "://" in website else f"https://{website}")
        return (parsed.netloc or parsed.path or "").lower().removeprefix("www.")
