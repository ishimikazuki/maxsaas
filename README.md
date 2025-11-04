# 営業リスト半自動作成アプリ

Python製CLIツールです。Googleスプレッドシートの企業リストを読み込み、公式サイト調査・連絡先抽出・AIレポート生成を自動化します。フロントエンドは不要で、営業担当者が行番号単位または一括で処理できます。

## 主な機能
- A列の `company_name` から公式サイトURLとドメインを特定
- 問い合わせフォーム、メールアドレス、電話・FAX、公式SNSを抽出
- 証跡URLを `evidence_sources` 列に集約
- OpenAI APIを利用した企業サマリー・主要サービス・最新ニュース・競合候補の生成
- 処理状況（`status` 列）と `_logs` シートへの実行ログ記録

## スプレッドシート仕様
対象シート（既定値: `prospects`）は以下の列構成を持ちます。

|列|項目|備考|
|---|---|---|
|A|company_name|企業名（必須）|
|B|resolved_domain|判定したドメイン|
|C|website_url|公式サイトURL|
|D|contact_form_url|問い合わせフォームURL|
|E|email_main|優先メール|
|F|email_role_based|ロールメール（`;`区切り）|
|G|email_guessed|推定メール（`;`区切り）|
|H|phone_main|電話番号（+81形式）|
|I|fax_main|FAX（+81形式）|
|J|sns_linkedin|公式LinkedIn|
|K|sns_x|公式X(Twitter)|
|L|sns_instagram|公式Instagram|
|M|sns_facebook|公式Facebook|
|N|evidence_sources|証跡URL（`|`区切り）|
|O|business_summary|200〜300文字サマリー|
|P|business_bullets|主要サービス（`;`区切り）|
|Q|recent_news|`YYYY-MM-DD|見出し|URL` 最大3件（改行区切り）|
|R|competitors_hint|競合候補（`;`区切り）|
|S|last_checked_at|ISO8601時刻（自動付与）|
|T|lock_manual_override|TRUEでロックし処理対象外|
|U|status|`pending` / `ok` / `needs_review` / `error`|
|V|error_detail|エラー・要確認メモ|

ログシート（既定値: `_logs`）には `[timestamp, stage, status, message, target_url]` を追記します。

## 必要な権限
- Google Sheets API: `https://www.googleapis.com/auth/spreadsheets`
- 探索用検索API（既定: Tavily Search API。Bing Search v7 / Google Custom Search も選択可）
- OpenAI API（企業レポート生成に使用）

## セットアップ
1. Python 3.10以上を用意。
2. 依存関係をインストール。
    ```bash
    pip install -e .[dev]
    ```
3. サービスアカウントJSONを作成し、対象スプレッドシートを共有します。
4. `.env` に設定を記述します。例：
    ```env
    SALES_LEAD_SPREADSHEET_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxx
    SALES_LEAD_MAIN_SHEET=prospects
    SALES_LEAD_LOG_SHEET=_logs
    SALES_LEAD_GCP_SERVICE_ACCOUNT=/path/to/service-account.json
    SALES_LEAD_SEARCH_PROVIDER=tavily
    TAVILY_API_KEY=your_tavily_key
    OPENAI_API_KEY=sk-...
    SALES_LEAD_MAX_SEARCH_RESULTS=5
    SALES_LEAD_MAX_PAGES=6
    ```
   Bing検索を使う場合は `SALES_LEAD_SEARCH_PROVIDER=bing` と `BING_SEARCH_API_KEY`、Google検索を使う場合は `GOOGLE_SEARCH_API_KEY` と `GOOGLE_SEARCH_CX` を設定してください。

## 使い方
```bash
# シート全体（pending/needs_review/error）を処理
sales-lead-builder run

# 行番号を指定して処理（ヘッダーを除く2行目以降）
sales-lead-builder run --row-number 5

# 会社名で1件処理
sales-lead-builder run --company "株式会社テスト"

# 既にstatus=okでも再処理（例: OpenAI設定後に再実行）
sales-lead-builder run --force

# Dry-run（シート更新せず挙動確認）
sales-lead-builder run --dry-run
```

## ステータス更新方針
- `ok`: URL・主要連絡先・レポート生成が成功。
- `needs_review`: 連絡先の一部不足、レポート未生成など確認が必要。
- `error`: 公式サイト未特定、検索APIエラーなど致命的な失敗。

## テスト
```bash
pytest
```

## フォルダ構成
```
.
├── pyproject.toml
├── README.md
├── src/
│   └── sales_lead_builder/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── google_sheets.py
│       ├── models.py
│       ├── processor.py
│       ├── reporting.py
│       ├── search_client.py
│       ├── site_scraper.py
│       └── site_selector.py
└── tests/
    ├── test_models.py
    ├── test_site_scraper.py
    └── test_site_selector.py
```

## 補足
- `OPENAI_API_KEY` を設定しない場合、レポート列は空のままで `needs_review` に更新されます。
- `lock_manual_override` 列が TRUE の行は処理対象外になります。
- 証跡URLは重複排除され `|` 区切りで格納されます。
