from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import phonenumbers
import requests
import tldextract
from bs4 import BeautifulSoup

from .config import Settings
from .models import ExtractionResult, PageContent

logger = logging.getLogger(__name__)


CONTACT_KEYWORDS = [
    "contact",
    "inquiry",
    "form",
    "お問い合わせ",
    "問合せ",
    "連絡",
    "資料請求",
]

ROLE_EMAIL_KEYWORDS = [
    "info",
    "sales",
    "support",
    "contact",
    "inquiry",
    "customer",
    "hello",
    "pr",
    "press",
    "ir",
]

SNS_PATTERNS: Dict[str, List[str]] = {
    "sns_linkedin": ["linkedin.com/company", "linkedin.com/in"],
    "sns_x": ["twitter.com", "x.com"],
    "sns_instagram": ["instagram.com"],
    "sns_facebook": ["facebook.com", "fb.me"],
}

EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:(?:\+?81[-\s]?)?0[0-9]{1,4}[-‐–―\s]?[0-9]{1,4}[-‐–―\s]?[0-9]{3,4})")


@dataclass(slots=True)
class PageFetcher:
    settings: Settings

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.user_agent})

    def fetch(self, url: str) -> Optional[PageContent]:
        try:
            response = self.session.get(url, timeout=self.settings.request_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return None
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        return PageContent(url=response.url, html=html, text=text)


class SiteCrawler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fetcher = PageFetcher(settings)

    def crawl(self, base_url: str) -> List[PageContent]:
        visited: Set[str] = set()
        results: List[PageContent] = []
        queue = deque([(base_url, 0)])
        base_host = urlparse(base_url).netloc

        while queue and len(results) < self.settings.crawler_max_pages:
            url, depth = queue.popleft()
            normalized_url = self._normalize_url(url)
            if normalized_url in visited:
                continue
            visited.add(normalized_url)

            page = self.fetcher.fetch(url)
            if not page:
                continue
            results.append(page)

            if depth >= self.settings.crawler_max_depth:
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                if not href:
                    continue
                abs_url = urljoin(page.url, href)
                parsed = urlparse(abs_url)
                if parsed.scheme not in {"http", "https"}:
                    continue
                if parsed.netloc != base_host:
                    continue
                if any(keyword in href.lower() for keyword in CONTACT_KEYWORDS):
                    queue.appendleft((abs_url, depth + 1))
                else:
                    queue.append((abs_url, depth + 1))
        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        normalized = parsed._replace(fragment="").geturl()
        return normalized


def pick_best_domain(url: str) -> str:
    extracted = tldextract.extract(url)
    parts = [p for p in [extracted.domain, extracted.suffix] if p]
    return ".".join(parts)


def extract_contact_info(pages: Iterable[PageContent], base_url: str) -> ExtractionResult:
    extraction = ExtractionResult()
    domain = urlparse(base_url).netloc
    evidence: Set[str] = set()

    for page in pages:
        soup = BeautifulSoup(page.html, "html.parser")
        # Contact form URL detection
        if not extraction.contact_form_url:
            link = _find_contact_link(soup, page.url)
            if link:
                extraction.contact_form_url = link
                evidence.add(link)

        # Emails
        emails = _extract_emails_from_page(soup)
        role_emails = [email for email in emails if _is_role_email(email)]
        if role_emails and not extraction.email_main:
            extraction.email_main = role_emails[0]
        if role_emails:
            extraction.email_role_based.extend(role_emails)
        elif emails and not extraction.email_main:
            extraction.email_main = emails[0]

        if emails:
            evidence.add(page.url)

        # Phone / Fax
        phone, fax = _extract_phone_fax(soup)
        if phone and not extraction.phone_main:
            extraction.phone_main = phone
            evidence.add(page.url)
        if fax and not extraction.fax_main:
            extraction.fax_main = fax
            evidence.add(page.url)

        # SNS
        sns_links = _extract_sns_links(soup, page.url)
        for key, value in sns_links.items():
            if key not in extraction.sns:
                extraction.sns[key] = value
                evidence.add(value)

    if not extraction.email_role_based:
        guessed = _guess_role_emails(domain)
        extraction.email_guessed.extend(guessed)
        if guessed and not extraction.email_main:
            extraction.email_main = guessed[0]
        evidence.update(guessed)

    extraction.email_role_based = sorted(set(extraction.email_role_based))
    extraction.email_guessed = sorted(set(extraction.email_guessed))
    extraction.evidence_sources = sorted(evidence)
    return extraction


def _find_contact_link(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    for anchor in soup.find_all("a", href=True):
        label = (anchor.get_text() or "").strip().lower()
        href = anchor.get("href")
        joined = urljoin(current_url, href)
        haystack = " ".join([label, href.lower()])
        if any(keyword in haystack for keyword in CONTACT_KEYWORDS):
            return joined
    return None


def _extract_emails_from_page(soup: BeautifulSoup) -> List[str]:
    emails: Set[str] = set()
    for mailto in soup.select("a[href^='mailto:']"):
        href = mailto.get("href")
        if href:
            email = href.split(":", 1)[1]
            if _is_email(email):
                emails.add(email.lower())
    text = soup.get_text(" ", strip=True)
    for match in EMAIL_PATTERN.findall(text):
        if _is_email(match):
            emails.add(match.lower())
    return sorted(emails)


def _is_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email.strip()))


def _is_role_email(email: str) -> bool:
    local_part = email.split("@", 1)[0]
    normalized = local_part.replace("-", "").replace("_", "").lower()
    return any(normalized.startswith(keyword) or keyword in normalized for keyword in ROLE_EMAIL_KEYWORDS)


def _extract_phone_fax(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    phone = None
    fax = None
    text_snippets = [string.strip() for string in soup.stripped_strings if string]
    for snippet in text_snippets:
        if "FAX" in snippet.upper() or "ＦＡＸ" in snippet:
            candidate = _normalize_phone(snippet)
            if candidate:
                fax = candidate
        elif any(keyword in snippet for keyword in ["TEL", "電話", "Phone", "電話番号"]):
            candidate = _normalize_phone(snippet)
            if candidate:
                phone = candidate
    if not phone or not fax:
        full_text = soup.get_text(" ", strip=True)
        for match in PHONE_PATTERN.findall(full_text):
            normalized = _normalize_phone(match)
            if normalized and not phone:
                phone = normalized
    return phone, fax


def _normalize_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"[^0-9+]", "", raw)
    if not digits:
        return None
    try:
        if digits.startswith("+"):
            parsed = phonenumbers.parse(digits, None)
        else:
            parsed = phonenumbers.parse(digits, "JP")
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None


def _extract_sns_links(soup: BeautifulSoup, current_url: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        abs_url = urljoin(current_url, href)
        lower = abs_url.lower()
        for key, patterns in SNS_PATTERNS.items():
            if any(pattern in lower for pattern in patterns):
                results[key] = abs_url
    return results


def _guess_role_emails(domain: str) -> List[str]:
    domain = domain.lower()
    if not domain:
        return []
    guesses = [
        f"info@{domain}",
        f"contact@{domain}",
        f"sales@{domain}",
        f"support@{domain}",
        f"inquiry@{domain}",
    ]
    return guesses
