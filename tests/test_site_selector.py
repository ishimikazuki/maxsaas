from __future__ import annotations

from sales_lead_builder.config import Settings
from sales_lead_builder.models import SearchResult
from sales_lead_builder.site_selector import OfficialSiteSelector


class DummyFetcher:
    def __init__(self, pages):
        self._pages = pages

    def fetch(self, url: str):
        return self._pages.get(url)


def test_official_site_selector_prefers_matching_domain(monkeypatch):
    settings = Settings(
        spreadsheet_id="dummy",
        google_service_account_file=None,
    )
    selector = OfficialSiteSelector(settings)

    from sales_lead_builder.site_selector import PageFetcher
    from sales_lead_builder.models import PageContent

    pages = {
        "https://example.co.jp": PageContent(
            url="https://example.co.jp",
            html="<html><head><title>Example株式会社 | 公式サイト</title></head><body>会社概要</body></html>",
            text="Example株式会社 公式サイト 会社概要",
        ),
        "https://other.com": PageContent(
            url="https://other.com",
            html="<html><body>Other site</body></html>",
            text="Other site",
        ),
    }

    monkeypatch.setattr(selector, "fetcher", DummyFetcher(pages))

    results = [
        SearchResult(title="Example", url="https://example.co.jp", rank=1),
        SearchResult(title="Other", url="https://other.com", rank=2),
    ]
    candidate = selector.select("Example株式会社", results)
    assert candidate is not None
    assert candidate.search_result.url == "https://example.co.jp"
