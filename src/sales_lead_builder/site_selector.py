from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

from .models import PageContent, SearchResult
from .site_scraper import CONTACT_KEYWORDS, PageFetcher, pick_best_domain
from .config import Settings

logger = logging.getLogger(__name__)

OFFICIAL_KEYWORDS = [
    "会社概要",
    "企業情報",
    "企業案内",
    "About",
    "Corporate",
    "沿革",
]


@dataclass(slots=True)
class SiteCandidate:
    search_result: SearchResult
    page: Optional[PageContent]
    score: float


class OfficialSiteSelector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fetcher = PageFetcher(settings)

    def select(self, company_name: str, candidates: Iterable[SearchResult]) -> Optional[SiteCandidate]:
        normalized_name = _normalize_company_name(company_name)
        best: Optional[SiteCandidate] = None
        for result in candidates:
            if not result.url:
                continue
            page = self.fetcher.fetch(result.url)
            if not page:
                continue
            score = self._score_candidate(normalized_name, page)
            if best is None or score > best.score:
                best = SiteCandidate(search_result=result, page=page, score=score)
            logger.debug("Candidate %s scored %.2f", result.url, score)
        return best

    def _score_candidate(self, normalized_name: str, page: PageContent) -> float:
        score = 0.0
        parsed = urlparse(page.url)
        hostname = parsed.hostname or ""
        if normalized_name and normalized_name in _normalize_company_name(hostname):
            score += 3.0
        title_match = re.search(re.escape(normalized_name), page.text, re.IGNORECASE)
        if title_match:
            score += 2.0
        for keyword in OFFICIAL_KEYWORDS:
            if keyword in page.text:
                score += 1.0
        if any(keyword in page.text for keyword in CONTACT_KEYWORDS):
            score += 0.5
        if hostname.endswith(".go.jp"):
            score -= 2.0  # governmental domains unlikely for private firms
        return score


def _normalize_company_name(name: str) -> str:
    normalized = name.lower()
    normalized = normalized.replace("株式会社", "")
    normalized = normalized.replace("有限会社", "")
    normalized = normalized.replace("inc.", "")
    normalized = normalized.replace("co., ltd.", "")
    normalized = re.sub(r"[^a-z0-9]", "", normalized)
    return normalized


__all__ = ["OfficialSiteSelector", "SiteCandidate", "pick_best_domain"]
