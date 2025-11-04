from __future__ import annotations

from sales_lead_builder.models import CompanyRow


def test_company_row_from_row_handles_missing_columns():
    row = CompanyRow.from_row(1, ["Acme Inc", "acme.jp", "https://acme.jp"])
    assert row.company_name == "Acme Inc"
    assert row.resolved_domain == "acme.jp"
    assert row.website_url == "https://acme.jp"
    assert row.status is None
    assert not row.lock_manual_override
