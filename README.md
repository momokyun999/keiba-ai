# 競馬AI予測ツール

LightGBMによる競馬単勝予測・展開予想ツール。

## セットアップ

```bash
pip install -r requirements.txt
```

## 起動方法

### Webアプリ（推奨）

```bash
streamlit run web_app.py
```

ブラウザで `http://localhost:8501` が開きます。

- **レース予想タブ**: race_id を入力して予想を実行
- **成績確認タブ**: 過去の予想記録と成績を確認

### CLIツール（従来）

```bash
python predict_live.py
```

## ファイル構成

```
keiba_app/
├── web_app.py             … Streamlit Webアプリ（メイン）
├── predict_live.py        … 予測ロジック（CLI兼インポート元）
├── app.py                 … 過去レース閲覧用アプリ（旧版）
├── train_models.py        … モデル学習スクリプト（Colab用）
├── requirements.txt       … 依存パッケージ
├── prediction_history.csv … 予想記録（自動生成）
└── model/                 … 学習済みモデル・成績DB
```

## 注意事項

- netkeibaへのスクレイピングを行います。過度な連続アクセスはしないでください。
- 予測結果は機械学習モデルによるものであり、的中を保証するものではありません。
- 馬券購入は自己責任でお楽しみください。
