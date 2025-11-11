# UI（環境変数＆実行パネル）

Streamlit ベースのシンプルなコントロールパネルです。`companydetail` / `companysearch` / `mailsend` の環境変数管理とコマンド実行をブラウザから行えます。

## セットアップ
1. 依存ライブラリをインストール
   ```bash
   cd /Users/akimare/FIXIM/GENai/sales-saas/ui
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. ルートディレクトリで以下を実行
   ```bash
   streamlit run ui/app.py
   ```

初回起動時に `ui/settings.json` が自動生成されます（APIキーなどはマスク付きで入力できます）。

## 画面の使い方
- **環境変数管理**: 各アプリで必要なキーをフォームに入力し「保存」。保存後は `settings.json` に安全に平文で保持され、実行時には自動で環境にロードされます。
- **アプリ実行**: ドロップダウンでアプリを選択し、必要なオプション（行番号、クエリ、ドライラン等）を設定して「実行」。裏側で既存CLIを呼び出し、標準出力をリアルタイムに表示します。
- 実行結果の確認は、従来通りGoogleスプレッドシートで行ってください。

## 注意
- CLIコマンド実行時には `companydetail/src` や `companysearch/src` を `PYTHONPATH` に自動設定します。
- APIキーなどの機密情報は `settings.json` に保存されるため、必要に応じて `.gitignore` 済みか確認してください（初期状態では `ui/settings.json` は未追跡です）。
