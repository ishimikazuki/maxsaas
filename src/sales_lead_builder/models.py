from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


SHEET_COLUMNS: Dict[str, str] = {
    "company_name": "A",
    "resolved_domain": "B",
    "website_url": "C",
    "contact_form_url": "D",
    "email_main": "E",
    "email_role_based": "F",
    "email_guessed": "G",
    "phone_main": "H",
    "fax_main": "I",
    "sns_linkedin": "J",
    "sns_x": "K",
    "sns_instagram": "L",
    "sns_facebook": "M",
    "evidence_sources": "N",
    "business_summary": "O",
    "business_bullets": "P",
    "recent_news": "Q",
    "competitors_hint": "R",
    "last_checked_at": "S",
    "lock_manual_override": "T",
    "status": "U",
    "error_detail": "V",
}


REPORT_FIELDS = [
    "business_summary",
    "business_bullets",
    "recent_news",
    "competitors_hint",
]


@dataclass(slots=True)
class CompanyRow:
    row_index: int  # zero-based for Sheets API
    company_name: str
    resolved_domain: Optional[str] = None
    website_url: Optional[str] = None
    contact_form_url: Optional[str] = None
    email_main: Optional[str] = None
    email_role_based: Optional[str] = None
    email_guessed: Optional[str] = None
    phone_main: Optional[str] = None
    fax_main: Optional[str] = None
    sns_linkedin: Optional[str] = None
    sns_x: Optional[str] = None
    sns_instagram: Optional[str] = None
    sns_facebook: Optional[str] = None
    evidence_sources: Optional[str] = None
    business_summary: Optional[str] = None
    business_bullets: Optional[str] = None
    recent_news: Optional[str] = None
    competitors_hint: Optional[str] = None
    last_checked_at: Optional[str] = None
    lock_manual_override: bool = False
    status: Optional[str] = None
    error_detail: Optional[str] = None

    @classmethod
    def from_row(cls, row_index: int, row_values: Iterable[str]) -> "CompanyRow":
        values = list(row_values)
        full_row: List[Optional[str]] = list(values) + [None] * (len(SHEET_COLUMNS) - len(values))
        mapping = list(SHEET_COLUMNS.keys())
        data: Dict[str, Optional[str]] = {
            mapping[i]: full_row[i] if i < len(full_row) else None for i in range(len(mapping))
        }

        def _clean(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            cleaned = str(value).strip()
            return cleaned or None

        lock_value = data.get("lock_manual_override") or ""
        return cls(
            row_index=row_index,
            company_name=_clean(data.get("company_name")) or "",
            resolved_domain=_clean(data.get("resolved_domain")),
            website_url=_clean(data.get("website_url")),
            contact_form_url=_clean(data.get("contact_form_url")),
            email_main=_clean(data.get("email_main")),
            email_role_based=_clean(data.get("email_role_based")),
            email_guessed=_clean(data.get("email_guessed")),
            phone_main=_clean(data.get("phone_main")),
            fax_main=_clean(data.get("fax_main")),
            sns_linkedin=_clean(data.get("sns_linkedin")),
            sns_x=_clean(data.get("sns_x")),
            sns_instagram=_clean(data.get("sns_instagram")),
            sns_facebook=_clean(data.get("sns_facebook")),
            evidence_sources=_clean(data.get("evidence_sources")),
            business_summary=_clean(data.get("business_summary")),
            business_bullets=_clean(data.get("business_bullets")),
            recent_news=_clean(data.get("recent_news")),
            competitors_hint=_clean(data.get("competitors_hint")),
            last_checked_at=_clean(data.get("last_checked_at")),
            lock_manual_override=lock_value.strip().lower() in {"true", "1", "yes"},
            status=_clean(data.get("status")),
            error_detail=_clean(data.get("error_detail")),
        )

    def to_update_payload(self, updates: Dict[str, Optional[str]]) -> Dict[str, str]:
        payload: Dict[str, str] = {}
        for field, value in updates.items():
            if field not in SHEET_COLUMNS:
                continue
            payload[field] = value or ""
        payload.setdefault("last_checked_at", datetime.now(timezone.utc).isoformat())
        return payload


@dataclass(slots=True)
class LogEntry:
    stage: str
    message: str
    target_url: Optional[str] = None
    status: str = "info"

    def to_row(self) -> List[str]:
        return [
            datetime.now(timezone.utc).isoformat(),
            self.stage,
            self.status,
            self.message,
            self.target_url or "",
        ]


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: Optional[str] = None
    rank: Optional[int] = None


@dataclass(slots=True)
class PageContent:
    url: str
    html: str
    text: str


@dataclass(slots=True)
class ExtractionResult:
    contact_form_url: Optional[str] = None
    email_main: Optional[str] = None
    email_role_based: List[str] = field(default_factory=list)
    email_guessed: List[str] = field(default_factory=list)
    phone_main: Optional[str] = None
    fax_main: Optional[str] = None
    sns: Dict[str, str] = field(default_factory=dict)
    evidence_sources: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ReportResult:
    business_summary: str
    business_bullets: List[str]
    recent_news: List[Dict[str, str]]
    competitors_hint: List[str]
