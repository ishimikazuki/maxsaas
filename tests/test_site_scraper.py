from __future__ import annotations

from bs4 import BeautifulSoup

from sales_lead_builder.models import PageContent
from sales_lead_builder.site_scraper import extract_contact_info


def _page(url: str, html: str) -> PageContent:
    soup = BeautifulSoup(html, "html.parser")
    return PageContent(url=url, html=html, text=soup.get_text(" ", strip=True))


def test_extract_contact_info_role_email_and_sns():
    home_html = """
    <html>
      <body>
        <a href="/contact">お問い合わせはこちら</a>
        <p>TEL : 03-1234-5678</p>
        <p>FAX：03-9876-5432</p>
        <a href="mailto:info@example.co.jp">info@example.co.jp</a>
        <a href="https://www.linkedin.com/company/example">LinkedIn</a>
        <a href="https://x.com/example">X</a>
      </body>
    </html>
    """
    contact_html = """
    <html>
      <body>
        <form action="/submit">フォーム</form>
        <p>メール: support@example.co.jp</p>
      </body>
    </html>
    """
    pages = [
        _page("https://example.co.jp", home_html),
        _page("https://example.co.jp/contact", contact_html),
    ]
    result = extract_contact_info(pages, "https://example.co.jp")
    assert result.contact_form_url == "https://example.co.jp/contact"
    assert result.email_main == "info@example.co.jp"
    assert "support@example.co.jp" in result.email_role_based
    assert result.phone_main == "+81312345678"
    assert result.fax_main == "+81398765432"
    assert result.sns["sns_linkedin"].startswith("https://www.linkedin.com/company/")
    assert result.sns["sns_x"].startswith("https://x.com/")
    assert result.email_guessed  # 予測アドレスも生成
    assert result.evidence_sources
