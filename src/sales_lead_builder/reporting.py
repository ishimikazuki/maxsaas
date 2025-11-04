from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from openai import OpenAI, OpenAIError

from .config import Settings
from .models import ReportResult, SearchResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReportGenerator:
    settings: Settings
    _client: OpenAI = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to generate reports")
        self._client = OpenAI(api_key=self.settings.openai_api_key)

    def generate(
        self,
        company_name: str,
        official_url: str,
        content_samples: Iterable[str],
        news_candidates: Iterable[SearchResult],
    ) -> ReportResult:
        prompt = self._build_prompt(company_name, official_url, content_samples, news_candidates)
        try:
            response = self._client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                top_p=self.settings.llm_top_p,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたは日本語で企業情報の要約を作成するアシスタントです。"
                            "必ず提供された公式情報のみを使用し、推測はしないでください。"
                            "出力は以下スキーマのJSONのみです。"
                            "{"
                            "\"business_summary\": 日本語200〜300文字の要約,"
                            "\"business_bullets\": 主要サービスを最大5件の配列 (各項目は50文字以内),"
                            "\"recent_news\": 最大3件の配列。各要素は {date: YYYY-MM-DD, headline: 30文字以内, url: 公式URL},"
                            "\"competitors_hint\": 同業他社候補を最大5件の配列"
                            "}"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except OpenAIError as exc:
            logger.error("Failed to call OpenAI: %s", exc)
            raise

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise RuntimeError("LLM returned empty response")
        data = json.loads(content)
        summary = data.get("business_summary", "").strip()
        bullets = [item.strip() for item in data.get("business_bullets", []) if item]
        news_items = []
        for item in data.get("recent_news", [])[:3]:
            date = (item.get("date") or "").strip()
            headline = (item.get("headline") or "").strip()
            url = (item.get("url") or "").strip()
            if date and headline and url:
                news_items.append({"date": date, "headline": headline, "url": url})
        competitors = [item.strip() for item in data.get("competitors_hint", []) if item]
        return ReportResult(
            business_summary=summary,
            business_bullets=bullets[:5],
            recent_news=news_items,
            competitors_hint=competitors[:5],
        )

    def _build_prompt(
        self,
        company_name: str,
        official_url: str,
        content_samples: Iterable[str],
        news_candidates: Iterable[SearchResult],
    ) -> str:
        snippets: List[str] = []
        for sample in content_samples:
            cleaned = (sample or "").strip()
            if cleaned:
                snippets.append(cleaned[:2000])
        news_lines: List[str] = []
        for result in news_candidates:
            if not result.url:
                continue
            headline = (result.title or "").strip()
            news_lines.append(f"{headline}\t{result.url}")
        prompt = (
            f"企業名: {company_name}\n"
            f"公式サイト: {official_url}\n"
            "---公式情報---\n"
            + "\n".join(snippets)
            + "\n---ニュース候補---\n"
            + "\n".join(news_lines)
            + "\n出力はJSONのみ。推測禁止。確証がない場合は配列を空にしてください。"
        )
        return prompt
