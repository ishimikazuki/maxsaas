from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from .config import Settings
from .models import SearchResult

logger = logging.getLogger(__name__)


class SearchClientError(RuntimeError):
    """Raised when the search provider fails."""


@dataclass(slots=True)
class SearchClient:
    settings: Settings

    def search_web(self, query: str, count: Optional[int] = None) -> List[SearchResult]:
        provider = (self.settings.search_provider or "bing").lower()
        max_results = count or self.settings.max_search_results
        if provider == "tavily":
            return self._tavily_search(query, max_results)
        if provider == "bing":
            return self._bing_search(query, max_results)
        if provider == "google":
            return self._google_search(query, max_results)
        raise SearchClientError(f"Unsupported search provider: {self.settings.search_provider}")

    def search_company(self, company_name: str) -> List[SearchResult]:
        keywords = [company_name, "公式", "会社概要"]
        query = " ".join(filter(None, keywords))
        return self.search_web(query)

    def search_company_news(self, company_name: str, max_results: int = 3) -> List[SearchResult]:
        query = f"{company_name} ニュース"
        results = self.search_web(query, count=max_results)
        return results[:max_results]

    def _bing_search(self, query: str, count: int) -> List[SearchResult]:
        if not self.settings.bing_api_key:
            raise SearchClientError("BING_SEARCH_API_KEY is required for Bing search")
        url = "https://api.bing.microsoft.com/v7.0/search"
        params = {
            "q": query,
            "count": count,
            "mkt": "ja-JP",
            "responseFilter": "Webpages",
            "safeSearch": "Moderate",
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.settings.bing_api_key,
            "User-Agent": self.settings.user_agent,
        }
        response = requests.get(url, params=params, headers=headers, timeout=self.settings.request_timeout)
        if response.status_code != 200:
            logger.error("Bing search failed: %s", response.text)
            raise SearchClientError(f"Bing search failed with status {response.status_code}")
        data = response.json()
        web_pages = data.get("webPages", {}).get("value", [])
        results: List[SearchResult] = []
        for idx, item in enumerate(web_pages):
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet"),
                    rank=idx + 1,
                )
            )
        return results

    def _tavily_search(self, query: str, count: int) -> List[SearchResult]:
        api_key = self.settings.tavily_api_key
        if not api_key:
            raise SearchClientError("TAVILY_API_KEY is required for Tavily search")
        url = "https://api.tavily.com/search"
        payload = {
            "query": query,
            "max_results": count,
            "search_depth": "advanced",
            "include_answer": False,
            "include_images": False,
            "include_raw_content": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.settings.user_agent,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=self.settings.request_timeout)
        if response.status_code != 200:
            logger.error("Tavily search failed: %s", response.text)
            raise SearchClientError(f"Tavily search failed with status {response.status_code}")
        data = response.json()
        results_data = data.get("results", [])
        results: List[SearchResult] = []
        for idx, item in enumerate(results_data):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content"),
                    rank=idx + 1,
                )
            )
        return results

    def _google_search(self, query: str, count: int) -> List[SearchResult]:
        if not (self.settings.google_search_api_key and self.settings.google_search_cx):
            raise SearchClientError("GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX are required for Google search")
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.settings.google_search_api_key,
            "cx": self.settings.google_search_cx,
            "q": query,
            "num": min(count, 10),
            "lr": "lang_ja",
        }
        headers = {"User-Agent": self.settings.user_agent}
        response = requests.get(url, params=params, headers=headers, timeout=self.settings.request_timeout)
        if response.status_code != 200:
            logger.error("Google Custom Search failed: %s", response.text)
            raise SearchClientError(f"Google search failed with status {response.status_code}")
        data = response.json()
        items = data.get("items", [])
        results: List[SearchResult] = []
        for idx, item in enumerate(items):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet"),
                    rank=idx + 1,
                )
            )
        return results
