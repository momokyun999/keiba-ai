"""
競馬 当日予想 統合スクリプト
========================================
出馬表URLを入力すると、出馬表をスクレイピングし、
過去成績DBと照合して、当日運用モデルで着順予想を出力する。

【使い方】
  python predict_live.py
  → race_id を入力するだけ

【データ取得方法の切り替え】
  get_shutuba() 関数だけを差し替えれば、
  netkeiba → JRA-VAN への移行が可能。
  下流の照合・予測処理は一切変更不要。
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pickle
import re
import time

# ===================================================
# 設定
# ===================================================
MODEL_DIR = "model/"   # モデル・DBの置き場所
REQUEST_WAIT = 1.0     # アクセス間隔（秒）：サーバー負荷軽減

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


# ===================================================
# 1. データ取得層（ここだけ差し替えれば取得方法を変更できる）
# ===================================================
def get_shutuba(race_id):
    """
    netkeibaの出馬表をスクレイピングしてDataFrameで返す。
    返す列は「共通データ形式」に統一されている。
    → JRA-VAN版を作るときも、同じ列を返せば下流は変更不要。
    """
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    time.sleep(REQUEST_WAIT)
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")

    # レース情報を取得
    race_info = _parse_race_info(soup, race_id)

    # 出馬表テーブルを取得
    table = soup.find("table", class_="Shutuba_Table")
    if table is None:
        raise ValueError("出馬表テーブルが見つかりません")

    horses = []
    for row in table.find_all("tr"):
        horse_data = _parse_horse_row(row)
        if horse_data:
            horses.append(horse_data)

    df = pd.DataFrame(horses)

    # レース共通情報を全馬に付与
    for key, val in race_info.items():
        df[key] = val

    df["entry_count"] = len(df)  # 出走頭数
    return df, race_info


def _parse_race_info(soup, race_id):
    """レース情報（距離・馬場・天気）を抽出"""
    info = {"race_id": race_id, "distance": None, "course_type": None,
            "weather": None, "track_condition": None, "venue": None,
            "race_name": None}

    # レース名
    race_name_el = soup.find("div", class_="RaceName")
    if race_name_el:
        info["race_name"] = race_name_el.get_text(strip=True)

    # コース・距離（例: "ダ1500m" "芝2000m"）
    data01 = soup.find("div", class_="RaceData01")
    if data01:
        text = data01.get_text(strip=True)
        # 距離
        dist_match = re.search(r"(\d+)m", text)
        if dist_match:
            info["distance"] = int(dist_match.group(1))
        # コース種別
        if "ダ" in text:
            info["course_type"] = "ダート"
        elif "芝" in text:
            info["course_type"] = "芝"
        elif "障" in text:
            info["course_type"] = "障害"
        # 天気
        for w in ["晴", "曇", "雨", "小雨", "雪", "小雪"]:
            if w in text:
                info["weather"] = w
                break
        # 馬場状態
        for t in ["良", "稍重", "重", "不良"]:
            if t in text:
                info["track_condition"] = t
                break

    return info


def _parse_horse_row(row):
    """1頭分のデータを抽出。ヘッダー行などはNoneを返す。"""
    horse_link = row.find("a", href=re.compile(r"/horse/"))
    if horse_link is None:
        return None

    cells = row.find_all("td")
    if len(cells) < 8:
        return None

    # horse_id
    horse_href = horse_link.get("href", "")
    hid_match = re.search(r"/horse/(\d+)", horse_href)
    horse_id = hid_match.group(1) if hid_match else None

    # 騎手名
    jockey_link = row.find("a", href=re.compile(r"/jockey/"))
    jockey_name = jockey_link.get_text(strip=True) if jockey_link else ""

    # 各セルのテキスト
    texts = [c.get_text(strip=True) for c in cells]

    # 馬体重（例: "410(-4)" → 410）
    horse_weight = None
    for t in texts:
        hw_match = re.match(r"(\d+)\(", t)
        if hw_match:
            horse_weight = int(hw_match.group(1))
            break

    # 性齢（例: "牝2"）
    sex_age = ""
    for t in texts:
        if re.match(r"[牡牝セ]\d", t):
            sex_age = t
            break

    # 斤量（例: "55.0"）
    weight = None
    for t in texts:
        if re.match(r"^\d{2}\.\d$", t):
            weight = float(t)
            break

    return {
        "horse_id": horse_id,
        "horse_name": horse_link.get_text(strip=True),
        "jockey_name": jockey_name,
        "frame": _safe_int(texts[0]) if len(texts) > 0 else None,
        "number": _safe_int(texts[1]) if len(texts) > 1 else None,
        "sex_age": sex_age,
        "weight": weight,
        "horse_weight": horse_weight,
    }


def _safe_int(text):
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


# ===================================================
# 1.5 オッズ取得層（netkeiba オッズAPIから取得）
# ===================================================
def get_odds(race_id):
    """
    netkeibaのオッズAPIから単勝オッズと人気を取得。
    返り値: {馬番(int): {'odds': float, 'popularity': int}}
    → JRA-VAN移行時はこの関数も差し替える。
    """
    api_url = (f"https://race.netkeiba.com/api/api_get_jra_odds.html"
               f"?race_id={race_id}&type=1")
    time.sleep(REQUEST_WAIT)
    res = requests.get(api_url, headers=HEADERS, timeout=10)
    data = res.json()

    odds_dict = {}
    try:
        if not isinstance(data, dict):
            raise TypeError(f"APIレスポンスが辞書でない: {type(data)}")
        tansho = data["data"]["odds"]["1"]  # "1" = 単勝
        for umaban_str, values in tansho.items():
            umaban = int(umaban_str)
            if not isinstance(values, (list, tuple)) or len(values) < 3:
                continue
            odds_val = float(values[0]) if values[0] not in ("", "0.0") else None
            pop_val = int(values[2]) if values[2] else None
            odds_dict[umaban] = {"odds": odds_val, "popularity": pop_val}
    except (KeyError, ValueError, IndexError, TypeError) as e:
        print(f"  オッズ解析エラー: {e}")

    return odds_dict


def merge_odds(df, race_id):
    """出馬表DataFrameにオッズと人気をマージ"""
    odds_dict = get_odds(race_id)

    if not odds_dict:
        print("  オッズ取得失敗 → 仮値で続行（予測精度低下）")
        df["odds"] = 1.0
        df["popularity"] = df["number"]
        return df

    df = df.copy()
    df["odds"] = df["number"].map(
        lambda n: odds_dict.get(int(n), {}).get("odds") if n is not None else None
    )
    df["popularity"] = df["number"].map(
        lambda n: odds_dict.get(int(n), {}).get("popularity") if n is not None else None
    )

    # 取消・除外馬を除く（オッズが負・0・極端に大きい、または人気が異常値）
    before = len(df)
    df = df[
        df["odds"].isna() |  # 後で補完される通常欠損は残す
        ((df["odds"] > 0) & (df["odds"] < 1000) &
         ((df["popularity"].isna()) | (df["popularity"] < 100)))
    ].copy()
    removed = before - len(df)
    if removed > 0:
        print(f"  → 取消・除外馬を除外: {removed}頭")

    n_odds = df["odds"].notna().sum()
    print(f"  → オッズ取得: {n_odds}頭 / {len(df)}頭")

    # 欠損は中央値で補完
    if df["odds"].isna().any():
        df["odds"] = df["odds"].fillna(df["odds"].median())
        df["popularity"] = df["popularity"].fillna(df["popularity"].max())

    return df


# ===================================================
# 1.6 レース結果取得層（着順照合用）
# ===================================================
_result_cache: dict = {}  # {race_id: {umaban: rank}} — プロセス内キャッシュ


def _fetch_race_results(race_id):
    """
    netkeibaの結果ページをスクレイピングして {馬番(int): 着順(int)} を返す。
    レース未確定・取得失敗時は空 dict を返す。
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    time.sleep(REQUEST_WAIT)
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", class_="RaceTable01")
        if table is None:
            return {}
        results = {}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            try:
                rank = int(cells[0].get_text(strip=True))
                umaban = int(cells[2].get_text(strip=True))
                results[umaban] = rank
            except (ValueError, IndexError):
                continue
        return results
    except Exception:
        return {}


def _fetch_result_rank(race_id, umaban):
    """
    指定レースの指定馬番の着順を返す。
    同一 race_id は1回だけスクレイピングしてキャッシュする。
    レース未確定・取得失敗時は None を返す。
    """
    race_id = str(race_id)
    if race_id not in _result_cache:
        _result_cache[race_id] = _fetch_race_results(race_id)
    return _result_cache[race_id].get(int(umaban))


# ===================================================
# 1.7 前走情報取得層
# ===================================================
def get_prev_race_info(horse_id):
    """前走情報を netkeiba API から取得。取得できない場合は None を返す。"""
    url = "https://db.netkeiba.com/horse/ajax_horse_results.html"
    params = {"id": horse_id, "input": "UTF-8", "output": "json"}
    headers_with_ref = {
        **HEADERS,
        "Referer": f"https://db.netkeiba.com/horse/{horse_id}/",
    }
    time.sleep(REQUEST_WAIT)
    try:
        res = requests.get(url, params=params, headers=headers_with_ref, timeout=10)
        data = res.json()
        html = data.get("data", "")
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="db_h_race_results")
        if table is None:
            return None
        rows = table.find_all("tr")
        if len(rows) < 2:
            return None
        cells = rows[1].find_all("td")

        def _cell_text(idx):
            return cells[idx].get_text(strip=True) if idx < len(cells) else ""

        def _to_int(text):
            try:
                return int(text)
            except (ValueError, TypeError):
                return None

        def _to_float(text):
            try:
                return float(text)
            except (ValueError, TypeError):
                return None

        prev_rank = _to_int(_cell_text(11))
        prev_last3f = _to_float(_cell_text(27))
        prev_popularity = _to_int(_cell_text(10))
        prev_date = _cell_text(0)

        if prev_rank is None and prev_last3f is None:
            return None

        return {
            "prev_rank": prev_rank,
            "prev_last3f": prev_last3f,
            "prev_popularity": prev_popularity,
            "prev_date": prev_date,
        }
    except Exception:
        return None


def merge_prev_race_info(df, progress_callback=None):
    """各馬の前走情報を取得して df に prev_rank, prev_last3f, prev_popularity 列を追加する。"""
    df = df.copy()
    total = len(df)
    prev_ranks, prev_last3fs, prev_pops = [], [], []

    for i, (_, row) in enumerate(df.iterrows()):
        horse_id = row.get("horse_id")
        if progress_callback:
            progress_callback(i + 1, total)
        else:
            print(f"\r  前走情報取得中... {i + 1}/{total}頭", end="", flush=True)

        info = get_prev_race_info(horse_id) if horse_id else None
        prev_ranks.append(info["prev_rank"] if info else None)
        prev_last3fs.append(info["prev_last3f"] if info else None)
        prev_pops.append(info["prev_popularity"] if info else None)

    if not progress_callback:
        print()

    df["prev_rank"] = pd.to_numeric(prev_ranks, errors="coerce")
    df["prev_last3f"] = pd.to_numeric(prev_last3fs, errors="coerce")
    df["prev_popularity"] = pd.to_numeric(prev_pops, errors="coerce")
    return df


def load_pattern_db(model_dir):
    """
    model/horse_pattern.parquet（各馬の立ち回りパターンDB）を読み込んで返す。
    列: horse_id, avg_pos_first, avg_pos_last, running_pattern, pattern_race_count
    無くても動くようにファイル欠損時は None を返す。
    """
    try:
        return pd.read_parquet(model_dir + "horse_pattern.parquet")
    except FileNotFoundError:
        return None


# ===================================================
# 2. 特徴量構築層（成績DB照合＋欠損補完）
# ===================================================
class FeatureBuilder:
    """出馬表DataFrameに過去成績を付与して特徴量を組み立てる"""

    def __init__(self, model_dir):
        self.horse_db = pd.read_parquet(model_dir + "horse_stats.parquet")
        self.jockey_db = pd.read_parquet(model_dir + "jockey_stats_byname.parquet")
        with open(model_dir + "global_means.pkl", "rb") as f:
            self.means = pickle.load(f)
        # 脚質DB（展開予想用）。無くても動くようにtry
        try:
            self.style_db = pd.read_parquet(model_dir + "horse_style.parquet")
        except FileNotFoundError:
            self.style_db = None
        # 立ち回りパターンDB（フェーズ別展開ストーリー用）
        self.pattern_db = load_pattern_db(model_dir)

    def _match_jockey(self, name):
        """騎手名を前方一致で照合"""
        clean = re.sub(r"[▲◎○△☆※消◇★\s]", "", name)
        exact = self.jockey_db[self.jockey_db["jockey_name"] == clean]
        if len(exact) > 0:
            return exact.iloc[0]["jockey_winrate"]
        prefix = self.jockey_db[self.jockey_db["jockey_name"].str.startswith(clean, na=False)]
        if len(prefix) > 0:
            best = prefix.sort_values("jockey_race_count", ascending=False).iloc[0]
            return best["jockey_winrate"]
        return None

    def build(self, df):
        """特徴量を構築。データなしは平均補完。"""
        df = df.copy()

        # --- 馬の成績を照合 ---
        df = df.merge(self.horse_db, on="horse_id", how="left")

        # --- 騎手の成績を照合 ---
        df["jockey_winrate"] = df["jockey_name"].apply(self._match_jockey)

        # --- 性齢を分解 ---
        df["sex"] = df["sex_age"].str[0]
        df["age"] = pd.to_numeric(df["sex_age"].str[1:], errors="coerce")
        sex_map = {"牡": 0, "牝": 1, "セ": 2}
        df["sex_code"] = df["sex"].map(sex_map).fillna(0)

        # --- カテゴリのコード化 ---
        weather_map = {"晴": 0, "曇": 1, "雨": 2, "小雨": 3, "雪": 4, "小雪": 5}
        track_map = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
        course_map = {"芝": 0, "ダート": 1, "障害": 2}
        df["weather_code"] = df["weather"].map(weather_map).fillna(0)
        df["track_code"] = df["track_condition"].map(track_map).fillna(0)
        df["course_type_code"] = df["course_type"].map(course_map).fillna(1)

        # --- 数値化 ---
        df["weight_num"] = pd.to_numeric(df["weight"], errors="coerce")
        df["horse_weight_num"] = pd.to_numeric(df["horse_weight"], errors="coerce")
        df["frame_num"] = pd.to_numeric(df["frame"], errors="coerce")
        df["number_num"] = pd.to_numeric(df["number"], errors="coerce")

        # --- 斤量差（レース平均との差） ---
        avg_weight = df["weight_num"].mean()
        df["weight_diff"] = df["weight_num"] - avg_weight

        # --- 成績特徴量の名前を合わせる（_safeを付ける） ---
        df["horse_winrate_safe"] = df["horse_winrate"]
        df["horse_top2rate_safe"] = df["horse_top2rate"]
        df["horse_top3rate_safe"] = df["horse_top3rate"]
        df["horse_avg_last3f_safe"] = df["horse_avg_last3f"]
        df["jockey_winrate_safe"] = df["jockey_winrate"]

        # --- 欠損補完（データなしの馬・騎手） ---
        fill_map = {
            "horse_winrate_safe": self.means["horse_winrate"],
            "horse_top2rate_safe": self.means["horse_top2rate"],
            "horse_top3rate_safe": self.means["horse_top3rate"],
            "horse_avg_last3f_safe": self.means["horse_avg_last3f"],
            "jockey_winrate_safe": self.means["jockey_winrate"],
        }
        for col, val in fill_map.items():
            df[col] = df[col].fillna(val)

        # データ不足フラグ（信頼度表示用）
        df["data_available"] = df["race_count"].fillna(0) > 0

        # 脚質を照合（展開予想用）
        if self.style_db is not None:
            df = df.merge(
                self.style_db[["horse_id", "main_style", "ratio_逃げ", "ratio_先行"]],
                on="horse_id", how="left"
            )
        else:
            df["main_style"] = None

        # --- 前走パフォーマンス指標（prev_outperform = 前走人気 − 前走着順）---
        if "prev_rank" in df.columns and "prev_popularity" in df.columns:
            df["prev_outperform"] = df["prev_popularity"] - df["prev_rank"]
            for col in ["prev_outperform", "prev_rank", "prev_last3f"]:
                if col in df.columns:
                    col_mean = df[col].mean()
                    df[col] = df[col].fillna(col_mean if pd.notna(col_mean) else 0)
        else:
            df["prev_outperform"] = 0
            df["prev_rank"] = 0
            df["prev_last3f"] = 0

        return df


# ===================================================
# 3. 予測層
# ===================================================
class Predictor:
    def __init__(self, model_dir):
        # 実力モード：オッズに依存しないモデルを常用する
        with open(model_dir + "model_no_odds.pkl", "rb") as f:
            self.model = pickle.load(f)
        with open(model_dir + "features_no_odds.pkl", "rb") as f:
            self.features = pickle.load(f)
        # 穴狙いモデル（オッズなし）。無くても動くようtry
        try:
            with open(model_dir + "model_no_odds.pkl", "rb") as f:
                self.model_ana = pickle.load(f)
            with open(model_dir + "features_no_odds.pkl", "rb") as f:
                self.features_ana = pickle.load(f)
        except FileNotFoundError:
            self.model_ana = None
            self.features_ana = None

    def predict(self, df):
        """予測を実行。oddsは事前にmerge_odds()で取得済みの前提。"""
        df = df.copy()

        # 万一oddsが無ければ仮値（通常はmerge_odds済み）
        if "odds" not in df.columns or df["odds"].isna().all():
            df["odds"] = df["odds"].fillna(1.0) if "odds" in df.columns else 1.0
        if "popularity" not in df.columns or df["popularity"].isna().all():
            df["popularity"] = df["number_num"]

        X = df[self.features].copy()
        if "odds" in self.features:
            X["odds"] = pd.to_numeric(X["odds"], errors="coerce").fillna(
                X["odds"].median() if "odds" in X else 1.0
            )

        proba = self.model.predict_proba(X)[:, 1]
        df["win_prob"] = proba

        # 穴狙いモデルのスコアも計算
        if self.model_ana is not None:
            X_ana = df[self.features_ana].copy()
            df["ana_prob"] = self.model_ana.predict_proba(X_ana)[:, 1]
            # 穴狙いモデルでのレース内順位
            df["ana_rank"] = df["ana_prob"].rank(ascending=False)

        return df.sort_values("win_prob", ascending=False).reset_index(drop=True)


# ===================================================
# 3.5 予想シナリオ生成（ルールベース）
# ===================================================

def build_pace_info(result):
    """脚質構成・前走データからペース情報 dict を生成する。"""
    entry_count = len(result)
    info = {
        "pace_str": "平均的なペース想定",
        "nige_count": 0,
        "senko_count": 0,
        "entry_count": entry_count,
        "nige_names": [],
        "fastest_last3f": None,
    }
    if "main_style" not in result.columns:
        return info

    style_counts = result["main_style"].dropna().value_counts().to_dict()
    nige = style_counts.get("逃げ", 0)
    senko = style_counts.get("先行", 0)
    front = nige + senko
    n = entry_count
    if nige >= 3:
        pace_str = "ハイペース濃厚（逃げ馬多数）→ 差し・追込有利"
    elif nige == 0:
        pace_str = "スローペース濃厚（逃げ馬不在）→ 前残り有利"
    elif front >= n * 0.5:
        pace_str = "前々の展開（先行勢多数）→ 力のある先行馬有利"
    else:
        pace_str = "平均的なペース想定"

    nige_names = []
    for _, r in result[result["main_style"] == "逃げ"].iterrows():
        num = r.get("number_num")
        name = r.get("horse_name")
        if name is None or (isinstance(name, float) and pd.isna(name)):
            continue
        if pd.notna(num):
            nige_names.append(f"{int(num)}番{name}")
        else:
            nige_names.append(str(name))

    fastest_last3f = None
    if "prev_last3f" in result.columns:
        valid = pd.to_numeric(result["prev_last3f"], errors="coerce")
        valid = valid[valid > 0]
        if len(valid) > 0:
            fastest_last3f = float(valid.min())

    info.update({
        "pace_str": pace_str,
        "nige_count": nige,
        "senko_count": senko,
        "nige_names": nige_names,
        "fastest_last3f": fastest_last3f,
    })
    return info


def _num_or_none(val):
    """値をfloatに変換する。欠損・変換不可はNoneを返す。"""
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def generate_scenario_comment(horse_row, role, pace_info):
    """
    ルールベースで予想シナリオの解説文を生成する。
    「①レース全体の展開予想 → ②その馬の有利・不利 → ③結論」の3部構成。

    horse_row : 馬の予測データ（pd.Series）
    role      : "本命" / "対抗" / "穴"
    pace_info : build_pace_info() の戻り値 dict
    """
    style_val = horse_row.get("main_style")
    style = (
        None
        if style_val is None or (isinstance(style_val, float) and pd.isna(style_val))
        else str(style_val)
    )
    win_prob = _num_or_none(horse_row.get("win_prob")) or 0.0
    popularity = _num_or_none(horse_row.get("popularity"))
    frame_num = _num_or_none(horse_row.get("frame_num"))
    prev_rank = _num_or_none(horse_row.get("prev_rank"))
    prev_last3f = _num_or_none(horse_row.get("prev_last3f"))
    top3rate = _num_or_none(horse_row.get("horse_top3rate_safe"))

    nige_count = pace_info.get("nige_count", 0)
    senko_count = pace_info.get("senko_count", 0)
    entry_count = pace_info.get("entry_count", 0)
    nige_names = pace_info.get("nige_names") or []
    fastest_last3f = pace_info.get("fastest_last3f")

    is_front = style in ("逃げ", "先行")
    is_closer = style in ("差し", "追込")

    sentences = []

    # ① レース全体の展開予想：逃げ馬頭数でペースを詳述
    if nige_count == 0:
        if senko_count > 0:
            sentences.append(
                f"逃げ馬不在で序盤のペース設定が不透明です。先行馬{senko_count}頭の中から"
                "誰かがハナを主張する流動的な展開が予想されます。"
            )
        else:
            sentences.append(
                "逃げ馬不在で序盤のペース設定が不透明です。先行争いも定まらず、"
                "序盤から混沌とした展開になりそうです。"
            )
    elif nige_count == 1:
        name = nige_names[0] if nige_names else "逃げ馬"
        sentences.append(
            f"{name}が単騎逃げの形が濃厚です。マイペースで運べれば粘り込みの可能性があります。"
        )
    elif nige_count == 2:
        sentences.append(
            "2頭の逃げ馬が主導権を争う形となり、ペースはやや速くなりそうです。"
        )
    else:
        sentences.append(
            f"逃げ馬{nige_count}頭が競り合い、ハイペース必至の消耗戦になる公算が大きいです。"
        )

    # ② 有利・不利：馬番×脚質
    if style is None:
        sentences.append("脚質データが不十分で、展開への適性は不透明です。")
    elif frame_num is None:
        if is_front:
            sentences.append("先行力を活かせるかどうかが、この馬にとって展開のポイントになります。")
        elif is_closer:
            sentences.append("末脚を生かせる展開になるかどうかが、この馬にとって鍵です。")
    elif frame_num <= 4:
        if is_front:
            sentences.append("内枠を活かして最短距離のコース取りが可能です。")
        elif is_closer:
            sentences.append("内枠でも差し脚質なら、包まれて進路を失うリスクがあります。")
    elif frame_num >= 11:
        if is_front:
            extra = "多頭数のため、なおさらポジション取りに苦労しそうです。" if entry_count >= 14 else ""
            sentences.append(f"外枠から先行するには距離ロスが懸念されます。{extra}".strip())
        elif is_closer:
            extra = "ただし多頭数だと展開の見極めがより重要になります。" if entry_count >= 14 else ""
            sentences.append(f"外枠から末脚を活かす形なら、枠の不利は少ないでしょう。{extra}".strip())
    else:
        if is_front:
            sentences.append("中枠から好位置を確保しやすく、位置取りの自由度があります。")
        elif is_closer:
            sentences.append("中枠なら内外どちらのコースも選択でき、進路を確保しやすいでしょう。")

    # ② 有利・不利：前走成績の加味（優先度順に1つ）
    if prev_rank is not None and prev_rank <= 3 and popularity is not None and popularity >= 5:
        sentences.append(
            f"前走{int(round(prev_rank))}着から人気が落ちており、狙い目のローテーションといえます。"
        )
    elif prev_rank is not None and prev_rank >= 8:
        sentences.append(
            f"前走{int(round(prev_rank))}着からの巻き返しを図りますが、敗因の分析が鍵となります。"
        )
    elif (
        fastest_last3f is not None
        and prev_last3f is not None
        and prev_last3f > 0
        and abs(prev_last3f - fastest_last3f) < 0.05
    ):
        sentences.append("前走の上がり最速は伏線です。末脚の破壊力は本物でしょう。")

    # ② 有利・不利：モデル評価と人気の乖離
    if win_prob >= 0.3 and popularity is not None and popularity >= 5:
        sentences.append(
            "市場では人気薄ですが、モデルの評価は高くオッズに妙味があります。"
        )
    elif win_prob <= 0.1 and popularity is not None and popularity <= 3:
        sentences.append(
            "人気に推されていますが、モデルの評価はそれほど高くありません。過信は禁物です。"
        )

    # 有利・不利パートが1文も無ければ最低限の補足を入れる（3〜5文を担保）
    if len(sentences) < 2:
        sentences.append("際立った特徴は少ないものの、堅実な走りが期待されます。")

    # ③ 結論：役割・モデル評価・複勝率から一言でまとめる
    if role == "本命":
        if win_prob >= 0.4 and top3rate is not None and top3rate >= 0.5:
            sentences.append("軸として高い信頼度があり、崩れる可能性は低いと言えます。")
        elif win_prob >= 0.3:
            sentences.append("モデル評価は最上位であり、軸として信頼できる存在です。")
        else:
            sentences.append("頭一つ抜けた存在とまでは言えず、過信は禁物です。")
    elif role == "対抗":
        if popularity is not None and popularity <= 2:
            sentences.append("人気の一角として支持は厚いものの、崩れれば共倒れのリスクもあります。")
        else:
            sentences.append("本命との評価差はわずかで、逆転の一発も十分にあり得ます。")
    else:  # 穴
        pop_str = f"{int(popularity)}番人気" if popularity is not None else "人気薄"
        if top3rate is not None and top3rate >= 0.35:
            sentences.append(
                f"市場評価は{pop_str}と低いものの複勝率は堅実で、軸抜きの一発に向く存在です。"
            )
        else:
            sentences.append(
                f"市場評価は{pop_str}と低く、展開が向けば一発はありますが、割引は必要です。"
            )

    return " ".join(sentences[:5])


def select_scenario_horses(result):
    """
    予測結果から本命・対抗・穴の3頭を選んで返す。
    戻り値: {"本命": pd.Series, "対抗": pd.Series, "穴": pd.Series or None}
    """
    honmei = result.iloc[0] if len(result) >= 1 else None
    taisho = result.iloc[1] if len(result) >= 2 else None

    ana = None
    if "ana_rank" in result.columns:
        res2 = result.copy()
        res2["_pop_num"] = pd.to_numeric(res2["popularity"], errors="coerce")
        candidates = res2[(res2["ana_rank"] == 1) & (res2["_pop_num"] >= 7)]
        if len(candidates) > 0:
            ana = candidates.iloc[0]

    return {"本命": honmei, "対抗": taisho, "穴": ana}


def _horse_label(row):
    """「{馬番}番{馬名}」形式の表示ラベルを作る。馬番が無ければ馬名のみ。"""
    num = row.get("number_num")
    name = row.get("horse_name")
    if pd.notna(num):
        return f"{int(num)}番{name}"
    return str(name)


def generate_race_story(result, pattern_db):
    """
    立ち回りパターンDBと脚質構成から、フェーズ別（序盤・中盤・直線）の
    展開ストーリーをルールベースで生成する。

    result     : Predictor.predict() の戻り値（main_style, number_num, horse_name, horse_id を含む）
    pattern_db : load_pattern_db() の戻り値（horse_id, avg_pos_first, running_pattern 等）

    戻り値: {"start": str, "middle": str, "stretch": str}
    """
    story = {"start": "", "middle": "", "stretch": ""}
    if pattern_db is None or "main_style" not in result.columns or len(result) == 0:
        return story

    df = result.copy()
    df["horse_id"] = df["horse_id"].astype(str)
    pdb = pattern_db.copy()
    pdb["horse_id"] = pdb["horse_id"].astype(str)
    pdb = pdb.drop_duplicates(subset="horse_id")
    df = df.merge(
        pdb[["horse_id", "avg_pos_first", "running_pattern"]],
        on="horse_id", how="left"
    )

    entry_count = len(df)
    style_counts = df["main_style"].dropna().value_counts().to_dict()
    nige_count = style_counts.get("逃げ", 0)
    senko_count = style_counts.get("先行", 0)
    front_ratio = (nige_count + senko_count) / entry_count if entry_count else 0.0
    nige_df = df[df["main_style"] == "逃げ"]

    # ▼ スタート〜序盤
    if nige_count == 0:
        story["start"] = (
            "逃げ馬不在で序盤のペース設定が不透明。"
            "先行力のある各馬が主導権を争う流動的なスタートが予想される。"
        )
    elif nige_count == 1:
        nige_row = nige_df.iloc[0]
        nige_name = _horse_label(nige_row)
        nige_horse_id = str(nige_row.get("horse_id"))
        zenme = df[
            (df["horse_id"] != nige_horse_id) &
            (pd.to_numeric(df["avg_pos_first"], errors="coerce") <= 0.35)
        ]
        zenme_names = [_horse_label(r) for _, r in zenme.head(3).iterrows()]
        zenme_str = "・".join(zenme_names) if zenme_names else "後続各馬"
        story["start"] = (
            f"{nige_name}がハナを主張し単騎逃げの形が濃厚。"
            f"{zenme_str}が2番手以降に続く隊列が予想される。"
        )
    elif nige_count == 2:
        n1 = _horse_label(nige_df.iloc[0])
        n2 = _horse_label(nige_df.iloc[1])
        story["start"] = (
            f"{n1}と{n2}がハナを争う展開。"
            "序盤からテンポが上がり縦長の隊列になりそう。"
        )
    else:
        story["start"] = (
            f"逃げ馬が{nige_count}頭と多く序盤から激しいハナ争いが予想される。"
            "テンポが上がり縦長の展開になりやすい。"
        )

    # ▼ 前半〜中盤
    if nige_count == 0:
        story["middle"] = (
            "スロー寄りの流れになりやすく先行勢が楽なペースで"
            "折り合う展開。差し・追込勢はじっくり脚を溜める形になりそう。"
        )
    elif nige_count == 1 and front_ratio < 0.4:
        story["middle"] = (
            "単騎逃げでペースはコントロールされやすく"
            "スロー〜平均ペースでの推移が濃厚。"
            "後続は自分のリズムで追走できる落ち着いた展開になりそう。"
        )
    elif front_ratio >= 0.5:
        story["middle"] = (
            "先行勢が多く前半からペースが緩みにくい展開。"
            "各馬が好位を取ろうと動くためペースは平均〜ハイになりやすい。"
            "後方勢は前との差を意識しながらの追走になる。"
        )
    else:
        story["middle"] = (
            "中盤は平均的なペースで推移する見込み。"
            "先行勢が前を固め差し・追込勢は中団から機会を伺う展開。"
        )

    # ▼ 直線
    if nige_count == 0 or (nige_count == 1 and front_ratio < 0.35):
        story["stretch"] = (
            "スローペースの影響で前残りの可能性が高い。"
            "差し・追込勢は直線での瞬発力勝負となるが"
            "前との差を詰められるかが焦点になる。"
        )
    elif nige_count >= 3 or front_ratio >= 0.5:
        story["stretch"] = (
            "前半のペースが響き逃げ・先行勢は直線で脚が鈍りやすい。"
            "末脚型が外から一気に突き抜けるシーンも十分考えられる。"
        )
    else:
        story["stretch"] = (
            "平均ペースからの直線は力のある馬が残りやすい。"
            "先行勢の粘りと差し勢の末脚が交錯する実力通りの決着になりやすい展開。"
        )

    return story


def _classify_pace_category(story):
    """generate_race_story() の直線コメントの文面から、パターン相性判定用の
    ペース区分（前残り展開 / 差し有利展開 / 平均ペース）を推定する。"""
    stretch = (story or {}).get("stretch", "")
    if "前残り" in stretch:
        return "前残り展開"
    if "末脚型が外から" in stretch:
        return "差し有利展開"
    return "平均ペース"


def generate_pattern_comment(horse_row, role, story, pattern_db):
    """
    馬の立ち回りパターン（running_pattern）と当日の展開ストーリーの相性、
    前走成績、モデル評価と人気の乖離、役割（本命/対抗/穴）を組み合わせて
    個別の解説コメントを生成する。

    horse_row  : 馬の予測データ（pd.Series。horse_id, horse_name, prev_rank,
                 win_prob, popularity を含む）
    role       : "本命" / "対抗" / "穴"
    story      : generate_race_story() の戻り値
    pattern_db : load_pattern_db() の戻り値
    """
    horse_name = horse_row.get("horse_name")

    running_pattern = None
    if pattern_db is not None:
        horse_id = str(horse_row.get("horse_id"))
        match = pattern_db[pattern_db["horse_id"].astype(str) == horse_id]
        if len(match) > 0:
            rp = match.iloc[0].get("running_pattern")
            if pd.notna(rp):
                running_pattern = str(rp)

    pace_category = _classify_pace_category(story)
    sentences = []

    # ① 立ち回りパターン × 展開の相性
    if pace_category == "前残り展開" and running_pattern == "逃げ・先行粘り込み型":
        sentences.append(
            f"スローペースは{horse_name}の得意な展開。"
            "先行して粘り込む形に持ち込めれば圧倒的に有利。"
        )
    elif pace_category == "前残り展開" and running_pattern in ("後方追込型", "後方待機型"):
        sentences.append(
            f"前残りの展開は{horse_name}にとって不利な条件。"
            "直線での爆発的な末脚に懸けることになる。"
        )
    elif pace_category == "差し有利展開" and running_pattern in ("後方追込型", "中団差し型"):
        sentences.append(
            f"ペースが上がれば{horse_name}の末脚が活きる展開。"
            "得意なパターンで力を発揮できる条件が揃った。"
        )
    elif pace_category == "差し有利展開" and running_pattern == "逃げ・先行粘り込み型":
        sentences.append(
            f"ペースが速くなると{horse_name}には厳しい条件。"
            "番手から早めに動く積極策が必要かもしれない。"
        )
    else:
        sentences.append(f"平均的な展開で{horse_name}の地力が問われる一戦。")

    # ② 前走成績
    prev_rank = _num_or_none(horse_row.get("prev_rank"))
    if prev_rank is not None and prev_rank <= 3:
        sentences.append(f"前走{int(round(prev_rank))}着と好調を維持しており上積みも期待できる。")
    elif prev_rank is not None and prev_rank >= 8:
        sentences.append(f"前走{int(round(prev_rank))}着からの巻き返しを狙う一戦となる。")

    # ③ モデル評価と人気の乖離
    win_prob = _num_or_none(horse_row.get("win_prob")) or 0.0
    popularity = _num_or_none(horse_row.get("popularity"))
    if win_prob >= 0.3 and popularity is not None and popularity >= 5:
        sentences.append("市場では人気薄だがモデルの評価は高くオッズに妙味がある。")
    elif win_prob <= 0.1 and popularity is not None and popularity <= 3:
        sentences.append("人気に推されているがモデルの評価はやや控えめ。過信は禁物。")

    # ④ role別の結論
    if role == "本命":
        sentences.append("総合的に見て軸として信頼できる一頭。")
    elif role == "対抗":
        sentences.append("本命を脅かす存在として馬券に絡める可能性が高い。")
    else:
        sentences.append("人気以上の実力を秘めており展開が向けば一発がある。")

    return " ".join(sentences)


# ===================================================
# 4. メイン処理
# ===================================================
def main():
    print("=" * 50)
    print("  競馬 当日予想ツール")
    print("=" * 50)
    race_id = input("\nrace_id を入力してください: ").strip()

    print("\n[1/5] 出馬表を取得中...")
    df_raw, race_info = get_shutuba(race_id)
    print(f"  → {len(df_raw)}頭の出馬表を取得")

    print("[2/5] オッズを取得中...")
    df_raw = merge_odds(df_raw, race_id)
    # 取消馬除外後の頭数で entry_count を更新
    df_raw["entry_count"] = len(df_raw)

    print("[3.5/5] 前走情報を取得中...")
    df_raw = merge_prev_race_info(df_raw)
    n_prev = df_raw["prev_rank"].notna().sum()
    print(f"  → 前走情報あり: {n_prev}頭 / データなし（新馬等）: {len(df_raw) - n_prev}頭")

    print("[4/5] 過去成績を照合中...")
    builder = FeatureBuilder(MODEL_DIR)
    df_feat = builder.build(df_raw)
    n_available = df_feat["data_available"].sum()
    print(f"  → 過去成績あり: {n_available}頭 / データなし: {len(df_feat) - n_available}頭")

    print("[5/5] 予測中...")
    predictor = Predictor(MODEL_DIR)
    result = predictor.predict(df_feat)

    # 結果表示
    print("\n" + "=" * 56)
    rn = race_info.get("race_name") or "レース"
    print(f"  {race_info.get('venue', '')} {rn}")
    print(f"  {race_info.get('course_type', '')}{race_info.get('distance', '')}m"
          f" / {race_info.get('weather', '?')} / 馬場:{race_info.get('track_condition', '?')}")
    print("=" * 56)
    print(f"\n{'予想':>3} {'馬番':>3} {'馬名':<14} {'脚質':>4} {'オッズ':>6} {'人気':>3} {'1着確率':>7} {'信頼度':>4}")
    print("-" * 64)
    for i, row in result.iterrows():
        conf = "○" if row["data_available"] else "△薄"
        odds_disp = f"{row['odds']:.1f}" if pd.notna(row['odds']) else "--"
        pop_disp = f"{int(row['popularity'])}" if pd.notna(row['popularity']) else "-"
        style = row.get("main_style") if pd.notna(row.get("main_style")) else "?"
        print(f"{i+1:>3} {int(row['number_num']):>3} "
              f"{str(row['horse_name']):<14} {style:>4} {odds_disp:>6} {pop_disp:>3} "
              f"{row['win_prob']:>6.1%} {conf:>4}")

    best = result.iloc[0]
    print(f"\n→ 本命: {int(best['number_num'])}番 {best['horse_name']}"
          f"（1着確率 {best['win_prob']:.1%} / {best['odds']:.1f}倍）")

    # ===== 展開予想 =====
    if "main_style" in result.columns:
        style_counts = result["main_style"].value_counts()
        nige = style_counts.get("逃げ", 0)
        senko = style_counts.get("先行", 0)

        print("\n【展開予想】")
        parts = []
        for s in ["逃げ", "先行", "差し", "追込"]:
            c = style_counts.get(s, 0)
            if c > 0:
                parts.append(f"{s}{c}頭")
        print(f"  脚質構成: {' / '.join(parts)}")

        # ペース予想（逃げ・先行馬の数で判定）
        front = nige + senko
        if nige >= 3:
            pace = "ハイペース濃厚（逃げ馬多数）→ 差し・追込有利"
        elif nige == 0:
            pace = "スローペース濃厚（逃げ馬不在）→ 前残り有利"
        elif front >= len(result) * 0.5:
            pace = "前々の展開（先行勢多数）→ 力のある先行馬有利"
        else:
            pace = "平均的なペース想定"
        print(f"  想定ペース: {pace}")

        # 逃げ馬を明示
        nige_horses = result[result["main_style"] == "逃げ"]
        if len(nige_horses) > 0:
            names = [f"{int(r['number_num'])}番{r['horse_name']}"
                     for _, r in nige_horses.iterrows()]
            print(f"  逃げ予想: {' , '.join(names)}")

    # ===== フェーズ別展開ストーリー =====
    story = generate_race_story(result, builder.pattern_db)
    if any(story.values()):
        print("\n" + "─" * 56)
        print("【フェーズ別展開ストーリー】")
        print(f"\n  ▼ スタート〜序盤\n    {story['start']}")
        print(f"\n  ▼ 前半〜中盤\n    {story['middle']}")
        print(f"\n  ▼ 直線\n    {story['stretch']}")

    # ===== 予想シナリオ =====
    pace_info = build_pace_info(result)
    scenarios = select_scenario_horses(result)
    print("\n" + "─" * 56)
    print("【予想シナリオ】")
    role_defs = [("◎", "本命"), ("○", "対抗"), ("★", "穴")]
    for mark, role in role_defs:
        horse = scenarios[role]
        if horse is None:
            if role == "穴":
                print("  穴シナリオ：このレースに穴狙い対象の馬はいません。")
            continue
        try:
            num = int(horse["number_num"])
        except (TypeError, ValueError):
            num = "?"
        name = horse["horse_name"]
        comment = generate_scenario_comment(horse, role, pace_info)
        print(f"\n  {mark} {role}：{num}番 {name}")
        print(f"    {comment}")
        if any(story.values()):
            pattern_comment = generate_pattern_comment(horse, role, story, builder.pattern_db)
            print(f"    [立ち回り×展開] {pattern_comment}")

    # ===== 穴狙い（実験的機能）=====
    # 「穴狙いモデルがレース内1位評価 × 人気薄」を検出
    # 検証結果（2023-2025年・テスト期間）:
    #   7番人気以下の単勝 → 回収率約138% / 的中率約4%
    #   7番人気以下の複勝 → 回収率約97% / 的中率約16%
    #   10番人気以下の複勝 → 回収率約109% / 的中率約9%
    if "ana_rank" in result.columns:
        result["popularity_num"] = pd.to_numeric(result["popularity"], errors="coerce")
        ana_pick = result[
            (result["ana_rank"] == 1) &
            (result["popularity_num"] >= 7)
        ]
        print("\n" + "─" * 56)
        print("【穴狙い（実験的機能）】")
        if len(ana_pick) > 0:
            for _, row in ana_pick.iterrows():
                pop = int(row["popularity_num"])
                print(f"  ◆ {int(row['number_num'])}番 {row['horse_name']}"
                      f"（{pop}番人気 / {row['odds']:.1f}倍）")
                print(f"    実力評価は高いが市場で過小評価されている馬")

                # 人気帯ごとに券種を推奨
                if pop >= 10:
                    print(f"    推奨: 複勝が手堅め（検証回収率109%/的中率9%）")
                    print(f"          単勝は一発狙い（検証回収率152%/的中率2%）")
                else:  # 7-9番人気
                    print(f"    推奨: 単勝が狙い目（検証回収率132%/的中率5%）")
                    print(f"          複勝なら当たりやすい（検証回収率93%/的中率18%）")
            print("\n  ※ いずれも過去検証値。連敗が続く前提の戦略です。")
            print("  ※ 趣味・実験用に少額での利用を推奨。利益は保証されません。")
        else:
            print("  該当馬なし（このレースに穴狙い対象はいません）")

    print("\n※ △薄は過去成績データが少なく予測精度が低い馬です。")


if __name__ == "__main__":
    main()