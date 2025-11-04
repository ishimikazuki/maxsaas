from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from google.auth import default
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings
from .models import CompanyRow, LogEntry, SHEET_COLUMNS

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


@dataclass(slots=True)
class SheetsClient:
    settings: Settings

    def __post_init__(self) -> None:
        self._credentials = self._build_credentials()
        self._service = build("sheets", "v4", credentials=self._credentials, cache_discovery=False)

    def _build_credentials(self):
        if self.settings.google_service_account_file:
            credentials = Credentials.from_service_account_file(
                self.settings.google_service_account_file,
                scopes=SHEETS_SCOPES,
            )
            if self.settings.google_subject:
                credentials = credentials.with_subject(self.settings.google_subject)
            return credentials
        credentials, _ = default(scopes=SHEETS_SCOPES)
        return credentials

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def fetch_rows(self, start_row: int = 2) -> List[CompanyRow]:
        sheet_range = f"{self.settings.main_sheet_name}!A{start_row}:V"
        response = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self.settings.spreadsheet_id, range=sheet_range)
            .execute()
        )
        values: List[List[str]] = response.get("values", [])
        rows: List[CompanyRow] = []
        for offset, raw in enumerate(values):
            row_index = start_row - 1 + offset
            rows.append(CompanyRow.from_row(row_index=row_index, row_values=raw))
        return rows

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def update_row(self, row: CompanyRow, updates: dict[str, Optional[str]]) -> None:
        filtered = {k: v for k, v in updates.items() if k in SHEET_COLUMNS and k != "lock_manual_override"}
        if not filtered:
            return
        row_number = row.row_index + 1
        data = []
        for field, value in filtered.items():
            column = SHEET_COLUMNS[field]
            range_name = f"{self.settings.main_sheet_name}!{column}{row_number}"
            data.append({"range": range_name, "values": [[value or "" ]]})
        body = {"valueInputOption": "USER_ENTERED", "data": data}
        (
            self._service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self.settings.spreadsheet_id, body=body)
            .execute()
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def append_log(self, entries: Iterable[LogEntry]) -> None:
        rows = [entry.to_row() for entry in entries]
        if not rows:
            return
        range_name = f"{self.settings.log_sheet_name}!A:E"
        body = {"values": rows}
        (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.settings.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    def ping(self) -> None:
        try:
            self.fetch_rows(start_row=1)
        except HttpError as exc:  # pragma: no cover - sanity check helper
            raise RuntimeError("Failed to access Google Sheets") from exc
