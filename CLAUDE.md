# CLAUDE.md — 競馬予測AIツール 開発指示書

このファイルは Claude Code への指示書です。
プロジェクトの背景・現状・依頼内容をまとめています。

---

## プロジェクト概要

機械学習（LightGBM）で競馬の単勝予測・展開予想を行うツール。
現在はCLI（コマンドライン）で動作しているが、**これをWebアプリ化したい**。

## 現在のファイル構成

```
keiba_app/
├── predict_live.py        … 当日予想ツール（CLI・メインロジック）
├── app.py                 … 既存のStreamlitアプリ（過去レース閲覧用）
├── train_models.py        … モデル学習スクリプト（Colab用・触らなくてよい）
├── requirements.txt       … 依存パッケージ
├── prediction_history.csv … 予想の記録（自動生成）
└── model/                 … 学習済みモデル・成績DB（触らなくてよい）
    ├── model_live.pkl
    ├── features_live.pkl
    ├── model_no_odds.pkl
    ├── features_no_odds.pkl
    ├── horse_stats.parquet
    ├── jockey_stats_byname.parquet
    ├── horse_style.parquet
    └── global_means.pkl
```

## predict_live.py の主要な関数（再利用してほしい）

ロジックは完成しているので、**これらの関数をimportして使うこと**。
予測ロジックを書き直す必要はない。

- `get_shutuba(race_id)` … 出馬表をスクレイピング → (DataFrame, race_info)
- `merge_odds(df, race_id)` … オッズをAPI取得してマージ
- `FeatureBuilder(MODEL_DIR)` … 過去成績を照合して特徴量を構築する class。`.build(df)` を持つ
- `Predictor(MODEL_DIR)` … 予測を行う class。`.predict(df)` を持つ。結果に `win_prob`, `main_style`（脚質）, `ana_rank`（穴狙い順位）列が付く
- `save_prediction(race_id, race_info, result)` … 予想をCSVに記録
- `update_results()` … 記録の結果照合・成績集計

## 依頼内容（Webアプリ化）

`predict_live.py` の予測ロジックをそのまま使い、**Streamlitで以下のWebアプリを作ってほしい**。
新規ファイル `web_app.py` として作成すること（既存の app.py は残す）。

### 必須機能

1. **レース予想ページ**
   - race_id をテキスト入力 → 「予想する」ボタン
   - 押すと `get_shutuba` → `merge_odds` → `FeatureBuilder.build` → `Predictor.predict` を順に実行
   - 結果を見やすい表で表示（予想順位・馬番・馬名・脚質・オッズ・人気・1着確率・信頼度）
   - 本命馬をハイライト表示
   - 展開予想（脚質構成・想定ペース・逃げ馬）を表示
   - 穴狙い候補があれば、リスク注記つきで表示
   - 予想実行時に `save_prediction` で自動記録

2. **成績ページ**
   - `prediction_history.csv` を読み込んで一覧表示
   - 「結果を照合する」ボタン → `update_results` を呼ぶ
   - 的中率・回収率を集計してメトリクス表示

### 設計上の注意

- 予測ロジックは predict_live.py からimportし、**重複実装しない**
- モデルの読み込みは `@st.cache_resource` でキャッシュし、毎回読み込まない
- スクレイピングには時間がかかるので、実行中はローディング表示（`st.spinner`）を出す
- エラー（race_idが不正・通信失敗）時はユーザーに分かりやすいメッセージを表示
- netkeibaへのアクセスは既存のWAIT間隔（REQUEST_WAIT）を尊重し、過度に繰り返さない

### UIの方針

- 日本語UI
- シンプルで見やすく。競馬新聞のような一覧性
- スマホでも見られるとなお良い

### 起動方法（READMEに追記してほしい）

```bash
streamlit run web_app.py
```

## やってほしくないこと

- model/ 配下のファイルやモデルの中身は変更しない
- predict_live.py の予測ロジック（数式・特徴量）は変更しない
  （UIから呼びやすいよう関数の引数を調整する程度はOK）
- 「必ず儲かる」等の誇大な表現をUIに入れない
  （穴狙いは実験的機能として、リスクを明示する既存の注記を踏襲）

## 補足：将来の展望（参考情報）

- データ取得は将来 netkeiba → JRA-VAN に切り替える可能性がある。
  そのため `get_shutuba` / `get_odds` を差し替えれば動く設計を維持してほしい。
