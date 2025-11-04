from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

import typer

from .config import get_settings
from .models import CompanyRow
from .processor import LeadProcessor

logging.basicConfig(level=logging.INFO)

app = typer.Typer(help="営業リスト半自動作成アプリ")


@app.command()
def run(
    row_number: Optional[int] = typer.Option(None, help="処理するシートの行番号 (1始まり)"),
    company: Optional[str] = typer.Option(None, help="会社名で1件処理"),
    limit: Optional[int] = typer.Option(None, help="処理件数の上限"),
    force: bool = typer.Option(False, help="status=okでも再処理"),
    dry_run: bool = typer.Option(False, help="シートを書き換えず結果のみ確認"),
) -> None:
    settings = get_settings()
    if dry_run:
        settings = replace(settings, dry_run=True)
    processor = LeadProcessor(settings)

    if row_number is not None:
        _process_single_row(processor, row_number)
        return
    if company:
        _process_by_company(processor, company)
        return

    outcomes = processor.process_sheet(force=force, limit=limit)
    _print_outcomes(outcomes)


def _process_single_row(processor: LeadProcessor, row_number: int) -> None:
    if row_number < 2:
        raise typer.BadParameter("ヘッダーを除く2行目以降を指定してください")
    rows = processor.sheets.fetch_rows(start_row=row_number)
    if not rows:
        typer.echo(f"行{row_number}はデータがありません")
        return
    row = rows[0]
    outcome = processor.process_row(row)
    _print_outcomes([outcome])


def _process_by_company(processor: LeadProcessor, company: str) -> None:
    rows = processor.sheets.fetch_rows()
    matches = [row for row in rows if row.company_name == company]
    if not matches:
        typer.echo(f"会社名 '{company}' は見つかりませんでした")
        raise typer.Exit(code=1)
    outcome = processor.process_row(matches[0])
    _print_outcomes([outcome])


def _print_outcomes(outcomes) -> None:
    for outcome in outcomes:
        row = outcome.row
        typer.echo(
            f"行{row.row_index + 1} {row.company_name}: status={outcome.updates.get('status')}"
        )
        if outcome.updates.get("error_detail"):
            typer.echo(f"  error_detail: {outcome.updates['error_detail']}")


if __name__ == "__main__":
    app()
