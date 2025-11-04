from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from urllib.parse import urlparse

from .config import Settings
from .google_sheets import SheetsClient
from .models import CompanyRow, ExtractionResult, LogEntry
from .reporting import ReportGenerator
from .search_client import SearchClient, SearchClientError
from .site_scraper import SiteCrawler, extract_contact_info, pick_best_domain
from .site_selector import OfficialSiteSelector

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_OK = "ok"
STATUS_REVIEW = "needs_review"
STATUS_ERROR = "error"


@dataclass(slots=True)
class ProcessOutcome:
    row: CompanyRow
    updates: dict[str, Optional[str]]
    logs: List[LogEntry]


@dataclass(slots=True)
class LeadProcessor:
    settings: Settings
    sheets: SheetsClient = field(init=False, repr=False)
    search: SearchClient = field(init=False, repr=False)
    selector: OfficialSiteSelector = field(init=False, repr=False)
    crawler: SiteCrawler = field(init=False, repr=False)
    report_generator: Optional[ReportGenerator] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.sheets = SheetsClient(self.settings)
        self.search = SearchClient(self.settings)
        self.selector = OfficialSiteSelector(self.settings)
        self.crawler = SiteCrawler(self.settings)
        self.report_generator: Optional[ReportGenerator]
        try:
            self.report_generator = ReportGenerator(self.settings)
        except ValueError:
            logger.warning("OPENAI_API_KEY not provided. Reports will require manual review.")
            self.report_generator = None

    def process_sheet(self, force: bool = False, limit: Optional[int] = None) -> List[ProcessOutcome]:
        rows = self.sheets.fetch_rows()
        outcomes: List[ProcessOutcome] = []
        for row in rows:
            if not row.company_name:
                continue
            if row.lock_manual_override:
                logger.info("Row %s locked; skipping", row.row_index + 1)
                continue
            if not force and row.status and row.status not in {STATUS_PENDING, STATUS_REVIEW, STATUS_ERROR}:
                continue
            outcome = self.process_row(row)
            outcomes.append(outcome)
            if limit and len(outcomes) >= limit:
                break
        return outcomes

    def process_row(self, row: CompanyRow) -> ProcessOutcome:
        logs: List[LogEntry] = []
        try:
            logger.info("Processing row %s: %s", row.row_index + 1, row.company_name)
            logs.append(LogEntry(stage="start", message=f"Processing {row.company_name}"))
            search_results = self._search_official_site(row.company_name)
            logs.append(LogEntry(stage="search", message=f"{len(search_results)} results"))

            candidate = self.selector.select(row.company_name, search_results)
            if not candidate or not candidate.page:
                raise RuntimeError("公式サイトを特定できませんでした")
            official_url = candidate.page.url
            resolved_domain = pick_best_domain(official_url)
            logs.append(LogEntry(stage="official_site", message=official_url, target_url=official_url))

            pages = self.crawler.crawl(official_url)
            extraction = extract_contact_info(pages, official_url)
            logs.append(LogEntry(stage="extract", message="contact info extracted", target_url=official_url))

            report = None
            if self.report_generator:
                snippets = [page.text[:1500] for page in pages[:3]]
                news_candidates = self._search_official_news(row.company_name, resolved_domain)
                report = self.report_generator.generate(
                    company_name=row.company_name,
                    official_url=official_url,
                    content_samples=snippets,
                    news_candidates=news_candidates,
                )
                logs.append(LogEntry(stage="report", message="LLM report generated"))

            updates = self._prepare_updates(row, official_url, resolved_domain, extraction, report)
            status = updates.get("status")
            if status == STATUS_ERROR:
                logs.append(LogEntry(stage="error", message=updates.get("error_detail", ""), status="error"))
            else:
                logs.append(LogEntry(stage="complete", message=status or STATUS_OK))

            if not self.settings.dry_run:
                self.sheets.update_row(row, updates)
                self.sheets.append_log(logs)
            return ProcessOutcome(row=row, updates=updates, logs=logs)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to process row %s", row.row_index + 1)
            error_updates = row.to_update_payload(
                {
                    "status": STATUS_ERROR,
                    "error_detail": str(exc),
                }
            )
            if not self.settings.dry_run:
                self.sheets.update_row(row, error_updates)
                logs.append(LogEntry(stage="exception", message=str(exc), status="error"))
                self.sheets.append_log(logs)
            return ProcessOutcome(row=row, updates=error_updates, logs=logs)

    def _search_official_site(self, company_name: str):
        try:
            return self.search.search_company(company_name)
        except SearchClientError as exc:
            raise RuntimeError("検索に失敗しました") from exc

    def _search_official_news(self, company_name: str, domain: str):
        try:
            results = self.search.search_company_news(company_name)
        except SearchClientError:
            return []
        filtered = []
        for result in results:
            parsed = urlparse(result.url)
            if parsed.netloc.endswith(domain):
                filtered.append(result)
        return filtered

    def _prepare_updates(
        self,
        row: CompanyRow,
        official_url: str,
        resolved_domain: str,
        extraction: ExtractionResult,
        report,
    ) -> dict[str, Optional[str]]:
        evidence_sources: List[str] = []
        if extraction.evidence_sources:
            evidence_sources.extend(extraction.evidence_sources)
        evidence_sources.append(official_url)
        evidence_str = "|".join(sorted(set(evidence_sources)))

        updates = {
            "resolved_domain": resolved_domain,
            "website_url": official_url,
            "contact_form_url": extraction.contact_form_url,
            "email_main": extraction.email_main,
            "email_role_based": ";".join(extraction.email_role_based) if extraction.email_role_based else None,
            "email_guessed": ";".join(extraction.email_guessed) if extraction.email_guessed else None,
            "phone_main": extraction.phone_main,
            "fax_main": extraction.fax_main,
            "sns_linkedin": extraction.sns.get("sns_linkedin"),
            "sns_x": extraction.sns.get("sns_x"),
            "sns_instagram": extraction.sns.get("sns_instagram"),
            "sns_facebook": extraction.sns.get("sns_facebook"),
            "evidence_sources": evidence_str,
            "status": STATUS_OK,
            "error_detail": None,
        }
        review_reasons: List[str] = []
        if report:
            updates.update(
                {
                    "business_summary": report.business_summary,
                    "business_bullets": ";".join(report.business_bullets),
                    "recent_news": "\n".join(
                        f"{item['date']}|{item['headline']}|{item['url']}" for item in report.recent_news
                    )
                    if report.recent_news
                    else None,
                    "competitors_hint": ";".join(report.competitors_hint) if report.competitors_hint else None,
                }
            )
        else:
            review_reasons.append("レポート未生成: OPENAI_API_KEY 未設定")

        if not extraction.email_main:
            review_reasons.append("メールアドレス未取得")
        if not extraction.phone_main:
            review_reasons.append("電話番号未取得")

        if review_reasons:
            updates["status"] = STATUS_REVIEW
            updates["error_detail"] = "; ".join(review_reasons)

        return row.to_update_payload(updates)
