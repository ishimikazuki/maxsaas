from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("settings.json")

ENV_FIELD_GROUPS: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "共通 (companydetail)",
        [
            ("SALES_LEAD_SPREADSHEET_ID", "GoogleシートID"),
            ("SALES_LEAD_MAIN_SHEET", "メインシート名"),
            ("SALES_LEAD_LOG_SHEET", "ログシート名"),
            ("SALES_LEAD_GCP_SERVICE_ACCOUNT", "GCPサービスアカウントJSONパス"),
            ("SALES_LEAD_GCP_SUBJECT", "G Suiteデリゲーション対象 (任意)"),
            ("SALES_LEAD_SEARCH_PROVIDER", "検索プロバイダ(tavily/bing/google)"),
            ("TAVILY_API_KEY", "Tavily API Key"),
            ("BING_SEARCH_API_KEY", "Bing API Key"),
            ("GOOGLE_SEARCH_API_KEY", "Google Search API Key"),
            ("GOOGLE_SEARCH_CX", "Google Custom Search CX"),
            ("OPENAI_API_KEY", "OpenAI API Key"),
            ("SALES_LEAD_MAX_SEARCH_RESULTS", "最大検索件数"),
            ("SALES_LEAD_MAX_PAGES", "クローラ最大ページ数"),
            ("SALES_LEAD_MAX_DEPTH", "クローラ最大深さ"),
            ("SALES_LEAD_USER_AGENT", "ユーザーエージェント"),
            ("SALES_LEAD_LLM_MODEL", "LLMモデル名"),
            ("SALES_LEAD_LLM_TEMPERATURE", "LLM温度"),
            ("SALES_LEAD_LLM_TOP_P", "LLM Top-p"),
        ],
    ),
    (
        "companysearch",
        [
            ("SHEET_ID", "GoogleシートID"),
            ("SHEET_NAME", "シート名"),
            ("START_ROW", "書き込み開始行"),
            ("MAX_RESULTS_PER_RUN", "1回あたりの最大書込件数"),
            ("REQUEST_TIMEOUT_SEC", "リクエストタイムアウト秒"),
            ("OPENAI_MODEL", "OpenAIモデル"),
            ("INPUT_QUERY", "デフォルト検索クエリ"),
            ("HOMEPAGE_RESOLVER", "公式URL解決手段"),
            ("COMPANY_SOURCE", "企業候補ソース"),
            ("GBIZINFO_API_KEY", "gBizINFO API Key"),
            ("SERPAPI_KEY", "SerpAPI Key"),
            ("GOOGLE_APPLICATION_CREDENTIALS", "Google認証JSONパス"),
        ],
    ),
    (
        "mailsend (SMTP)",
        [
            ("SMTP_HOST", "SMTPホスト"),
            ("SMTP_PORT", "SMTPポート"),
            ("SMTP_USER", "SMTPユーザー"),
            ("SMTP_PASSWORD", "SMTPパスワード"),
            ("SMTP_SENDER", "送信者メール"),
            ("SMTP_SENDER_NAME", "送信者名"),
            ("SMTP_SECURITY", "セキュリティ(starttls/ssl/none)"),
        ],
    ),
]

SENSITIVE_KEYS = {
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "BING_SEARCH_API_KEY",
    "GOOGLE_SEARCH_API_KEY",
    "GBIZINFO_API_KEY",
    "SERPAPI_KEY",
    "SMTP_PASSWORD",
}

DEFAULT_CONFIG: Dict[str, str] = {
    "SALES_LEAD_MAIN_SHEET": "prospects",
    "SALES_LEAD_LOG_SHEET": "_logs",
    "SALES_LEAD_SEARCH_PROVIDER": "tavily",
    "SALES_LEAD_MAX_SEARCH_RESULTS": "5",
    "SALES_LEAD_MAX_PAGES": "6",
    "SALES_LEAD_MAX_DEPTH": "2",
    "SALES_LEAD_LLM_MODEL": "gpt-4o-mini",
    "SALES_LEAD_LLM_TEMPERATURE": "0.1",
    "SALES_LEAD_LLM_TOP_P": "0.9",
    "SHEET_NAME": "prospects",
    "START_ROW": "2",
    "MAX_RESULTS_PER_RUN": "20",
    "REQUEST_TIMEOUT_SEC": "30",
    "OPENAI_MODEL": "gpt-4o-mini",
    "HOMEPAGE_RESOLVER": "tavily",
    "COMPANY_SOURCE": "openai",
    "SMTP_PORT": "587",
    "SMTP_SECURITY": "starttls",
}


def load_config() -> Dict[str, str]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    data = DEFAULT_CONFIG.copy()
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def save_config(data: Dict[str, str]) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def initialize_session_state(config: Dict[str, str]) -> None:
    for group, fields in ENV_FIELD_GROUPS:
        for key, _ in fields:
            state_key = f"env_{key}"
            if state_key not in st.session_state:
                st.session_state[state_key] = config.get(key, DEFAULT_CONFIG.get(key, ""))


def build_command(app: str, params: Dict[str, str]) -> Tuple[List[str], Path, Dict[str, str]]:
    env = os.environ.copy()
    config = load_config()
    env.update({k: v for k, v in config.items() if v})

    if app == "companydetail":
        cmd = ["python3", "-m", "sales_lead_builder.cli", "run"]
        if params.get("row_number"):
            cmd += ["--row-number", str(int(params["row_number"]))]
        if params.get("company_name"):
            cmd += ["--company", params["company_name"]]
        if params.get("limit"):
            cmd += ["--limit", str(int(params["limit"]))]
        if params.get("force"):
            cmd.append("--force")
        if params.get("dry_run"):
            cmd.append("--dry-run")
        env["PYTHONPATH"] = str((ROOT_DIR / "companydetail" / "src").resolve())
        cwd = ROOT_DIR / "companydetail"
    elif app == "companysearch":
        cmd = ["python3", "-m", "companysearch.cli"]
        if params.get("query"):
            cmd += ["--query", params["query"]]
        if params.get("log_level"):
            cmd += ["--log-level", params["log_level"]]
        env["PYTHONPATH"] = str((ROOT_DIR / "companysearch" / "src").resolve())
        cwd = ROOT_DIR / "companysearch"
    elif app == "mailsend":
        cmd = ["python3", "send_bulk_mail.py"]
        if params.get("contacts"):
            cmd += ["--contacts", params["contacts"]]
        if params.get("defaults"):
            cmd += ["--defaults", params["defaults"]]
        if params.get("limit"):
            cmd += ["--limit", str(int(params["limit"]))]
        if params.get("subject"):
            cmd += ["--subject", params["subject"]]
        if params.get("archive_dir"):
            cmd += ["--archive-dir", params["archive_dir"]]
        if params.get("dry_run"):
            cmd.append("--dry-run")
        cwd = ROOT_DIR / "mailsend"
    else:
        raise ValueError("未対応のアプリです")

    return cmd, cwd, env


def run_command(cmd: List[str], cwd: Path, env: Dict[str, str]) -> Tuple[int, str]:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: List[str] = []
    placeholder = st.empty()
    for line in process.stdout or []:
        output_lines.append(line)
        placeholder.code("".join(output_lines), language="bash")
    return_code = process.wait()
    full_output = "".join(output_lines)
    placeholder.code(full_output or "(出力なし)", language="bash")
    return return_code, full_output


def main() -> None:
    st.set_page_config(page_title="Sales SaaS Automation UI", layout="wide")
    config = load_config()
    initialize_session_state(config)

    st.title("Sales Ops コントロールパネル")
    st.caption("環境変数の管理と既存CLIアプリの実行をブラウザから行います")

    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("環境変数管理")
        with st.form("env_form"):
            updated: Dict[str, str] = {}
            for group, fields in ENV_FIELD_GROUPS:
                st.markdown(f"**{group}**")
                for key, label in fields:
                    value = st.text_input(
                        label,
                        value=st.session_state[f"env_{key}"],
                        key=f"input_{key}",
                        type="password" if key in SENSITIVE_KEYS else "default",
                    )
                    updated[key] = value
            if st.form_submit_button("保存"):
                for key, value in updated.items():
                    st.session_state[f"env_{key}"] = value
                    config[key] = value
                save_config(config)
                st.success("保存しました")

    with col2:
        st.subheader("アプリ実行")
        app_choice = st.selectbox("アプリを選択", ["companydetail", "companysearch", "mailsend"])

        run_params: Dict[str, str] = {}
        if app_choice == "companydetail":
            run_params["row_number"] = st.number_input("行番号 (任意)", min_value=0, value=0)
            run_params["company_name"] = st.text_input("会社名 (任意)")
            run_params["limit"] = st.number_input("limit (任意)", min_value=0, value=0)
            run_params["force"] = st.checkbox("force 再処理")
            run_params["dry_run"] = st.checkbox("dry-run")
        elif app_choice == "companysearch":
            run_params["query"] = st.text_input("検索クエリ", value=config.get("INPUT_QUERY", ""))
            run_params["log_level"] = st.selectbox("ログレベル", ["DEBUG", "INFO", "WARNING", "ERROR"], index=1)
        elif app_choice == "mailsend":
            run_params["contacts"] = st.text_input("連絡先CSVパス", value="contacts.sample.csv")
            run_params["defaults"] = st.text_input("defaults JSONパス", value="defaults.sample.json")
            run_params["limit"] = st.number_input("送信件数limit (0は制限なし)", min_value=0, value=0)
            run_params["subject"] = st.text_input("件名テンプレ (任意)")
            run_params["archive_dir"] = st.text_input("EML保存ディレクトリ (空で無効)", value="outbox")
            run_params["dry_run"] = st.checkbox("dry-run", value=True)

        if st.button("実行"):
            filtered_params = {k: v for k, v in run_params.items() if v not in ("", 0, None)}
            try:
                cmd, cwd, env = build_command(app_choice, filtered_params)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.info("コマンド: " + " ".join(cmd))
                with st.spinner("実行中..."):
                    code, logs = run_command(cmd, cwd, env)
                if code == 0:
                    st.success("完了しました。結果はスプレッドシートでご確認ください。")
                else:
                    st.error(f"コマンドが失敗しました (exit {code})")

    st.markdown("---")
    st.caption(
        "保存済み設定ファイル: " + str(CONFIG_PATH)
    )


if __name__ == "__main__":
    main()
