from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    spreadsheet_id: str
    main_sheet_name: str = "prospects"
    log_sheet_name: str = "_logs"
    google_service_account_file: Optional[str] = None
    google_subject: Optional[str] = None
    search_provider: str = "tavily"  # "tavily", "bing", or "google"
    tavily_api_key: Optional[str] = None
    bing_api_key: Optional[str] = None
    google_search_api_key: Optional[str] = None
    google_search_cx: Optional[str] = None
    openai_api_key: Optional[str] = None
    request_timeout: int = 15
    max_search_results: int = 5
    crawler_max_pages: int = 6
    crawler_max_depth: int = 2
    user_agent: str = field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_top_p: float = 0.9
    dry_run: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        spreadsheet_id = os.getenv("SALES_LEAD_SPREADSHEET_ID")
        if not spreadsheet_id:
            raise ValueError("Environment variable SALES_LEAD_SPREADSHEET_ID is required")

        return cls(
            spreadsheet_id=spreadsheet_id,
            main_sheet_name=os.getenv("SALES_LEAD_MAIN_SHEET", "prospects"),
            log_sheet_name=os.getenv("SALES_LEAD_LOG_SHEET", "_logs"),
            google_service_account_file=os.getenv("SALES_LEAD_GCP_SERVICE_ACCOUNT"),
            google_subject=os.getenv("SALES_LEAD_GCP_SUBJECT"),
            search_provider=os.getenv("SALES_LEAD_SEARCH_PROVIDER", "tavily"),
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            bing_api_key=os.getenv("BING_SEARCH_API_KEY"),
            google_search_api_key=os.getenv("GOOGLE_SEARCH_API_KEY"),
            google_search_cx=os.getenv("GOOGLE_SEARCH_CX"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            request_timeout=int(os.getenv("SALES_LEAD_REQUEST_TIMEOUT", "15")),
            max_search_results=int(os.getenv("SALES_LEAD_MAX_SEARCH_RESULTS", "5")),
            crawler_max_pages=int(os.getenv("SALES_LEAD_MAX_PAGES", "6")),
            crawler_max_depth=int(os.getenv("SALES_LEAD_MAX_DEPTH", "2")),
            user_agent=os.getenv(
                "SALES_LEAD_USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36",
            ),
            llm_model=os.getenv("SALES_LEAD_LLM_MODEL", "gpt-4o-mini"),
            llm_temperature=float(os.getenv("SALES_LEAD_LLM_TEMPERATURE", "0.1")),
            llm_top_p=float(os.getenv("SALES_LEAD_LLM_TOP_P", "0.9")),
            dry_run=os.getenv("SALES_LEAD_DRY_RUN", "false").lower() in {"1", "true", "yes"},
        )


def get_settings() -> Settings:
    return Settings.from_env()
