"""
競馬AI予測 Webアプリ
predict_live.py の予測ロジックをそのまま使って Streamlit で動作する。
起動: streamlit run web_app.py
"""
import html as _html_mod
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from predict_live import (
    MODEL_DIR,
    FeatureBuilder,
    Predictor,
    get_shutuba,
    merge_odds,
    merge_prev_race_info,
    _fetch_result_rank,
    build_pace_info,
    generate_scenario_comment,
    generate_race_story,
    generate_pattern_comment,
    select_scenario_horses,
)

HISTORY_CSV = "prediction_history.csv"

st.set_page_config(
    page_title="競馬AI予測",
    page_icon="🐎",
    layout="wide",
)

# ===================================================
# カスタムCSS
# ===================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

#MainMenu, footer, [data-testid="stHeader"] { display: none !important; }

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans JP', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #1A1A1A;
    font-size: 16px !important;
}
.stApp { background: #F5F5F7 !important; }
.main .block-container { padding: 0 3rem 4rem !important; max-width: 1140px !important; }

/* ─── Hero Header ─── */
.hero-header { padding: 2.5rem 0 0.625rem; }
.hero-title {
    font-size: 2.75rem; font-weight: 800; letter-spacing: -0.04em;
    color: #1A1A1A; margin: 0; line-height: 1.15;
}
.hero-tagline { font-size: 1.25rem; font-weight: 500; color: #6B7280; margin-top: 0.625rem; letter-spacing: -0.01em; }
.hero-divider { border: none; border-top: 1px solid #EBEBED; margin: 0.875rem 0 1rem; }

/* ─── Sidebar ─── */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #EBEBED; }
[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
.sidebar-brand { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; padding: 0 0.25rem; }
.sidebar-brand-icon { font-size: 2.25rem; line-height: 1; }
.sidebar-brand-title { font-size: 1.375rem; font-weight: 800; letter-spacing: -0.02em; color: #1A1A1A; }
.sidebar-divider { border: none; border-top: 1px solid #EBEBED; margin: 1.25rem 0; }
[data-testid="stSidebar"] .stCaption p { font-size: 0.75rem !important; color: #9CA3AF !important; line-height: 1.6; margin-bottom: 0.5rem; }
[data-testid="stSidebar"] .stButton > button { justify-content: flex-start !important; margin-bottom: 0.5rem !important; }

/* ─── Cards ─── */
.card {
    background: #fff; border-radius: 16px; padding: 1.5rem 1.75rem; margin-bottom: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 16px -4px rgba(0,0,0,0.07);
    border: 1px solid rgba(0,0,0,0.04);
}
.card-label {
    font-size: 0.6875rem; font-weight: 600; color: #9CA3AF;
    text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;
}

/* ─── Race Header Card ─── */
.race-header-card {
    background: linear-gradient(135deg, #312E81 0%, #4F46E5 55%, #818CF8 100%);
    border-radius: 16px; padding: 1.75rem 2rem; margin-bottom: 1.25rem; color: white;
    box-shadow: 0 4px 20px -4px rgba(79,70,229,0.4);
}
.race-venue-label { font-size: 0.6875rem; font-weight: 600; color: rgba(255,255,255,0.55); text-transform: uppercase; letter-spacing: 0.1em; margin: 0; }
.race-name { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.025em; margin: 0.25rem 0 1rem; }
.race-meta { display: flex; gap: 1.25rem; flex-wrap: wrap; }
.race-meta-item { font-size: 0.8125rem; color: rgba(255,255,255,0.8); }

/* ─── Honmei Card ─── */
.honmei-card {
    display: flex; align-items: center; gap: 1.25rem; background: #EEF2FF;
    border: 1.5px solid #C7D2FE; border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
}
.honmei-mark { font-size: 2rem; font-weight: 700; color: #4F46E5; line-height: 1; flex-shrink: 0; }
.honmei-label-text { font-size: 0.6875rem; font-weight: 600; color: #818CF8; text-transform: uppercase; letter-spacing: 0.09em; }
.honmei-horse-name { font-size: 1.3rem; font-weight: 700; color: #1A1A1A; letter-spacing: -0.02em; margin: 0.125rem 0 0.375rem; }
.honmei-stats { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; }
.stat-primary { font-size: 0.875rem; font-weight: 600; color: #4F46E5; }
.stat-muted   { font-size: 0.8125rem; color: #818CF8; }

/* ─── Prediction Table ─── */
.pred-table-wrap { overflow-x: auto; }
.pred-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; color: #1A1A1A; }
.pred-table thead tr { background: #F9FAFB; }
.pred-table th {
    padding: 0.625rem 0.875rem; text-align: left; font-size: 0.6875rem; font-weight: 600;
    color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.07em;
    border-bottom: 1px solid #EBEBED; white-space: nowrap;
}
.pred-table td { padding: 0.75rem 0.875rem; border-bottom: 1px solid #F5F5F7; vertical-align: middle; }
.pred-table tr:last-child td { border-bottom: none; }
.pred-table tr.hr-row td { background: #FAFAFF; }
.pred-table tr.hr-row td:first-child { border-left: 3px solid #4F46E5; padding-left: calc(0.875rem - 3px); }
.pred-table tbody tr:hover td { background: #FCFCFE; }

.mk { font-weight: 700; font-size: 1rem; }
.mk-h { color: #4F46E5; }
.mk-t { color: #059669; }
.mk-s { color: #D97706; }
.mk-a { color: #DC2626; }

.sb { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 5px; font-size: 0.75rem; font-weight: 600; }
.sb-nige   { background: #FEE2E2; color: #991B1B; }
.sb-senkou { background: #FEF3C7; color: #92400E; }
.sb-sashi  { background: #DBEAFE; color: #1E40AF; }
.sb-oikomi { background: #EDE9FE; color: #5B21B6; }
.sb-other  { background: #F3F4F6; color: #374151; }

.prob-cell { display: flex; flex-direction: column; gap: 0.25rem; min-width: 90px; }
.prob-text  { font-size: 0.875rem; font-weight: 600; }
.prob-track { width: 80px; height: 5px; background: #E5E7EB; border-radius: 3px; overflow: hidden; }
.prob-fill  { height: 100%; background: linear-gradient(90deg, #A5B4FC, #4F46E5); border-radius: 3px; }

.tdot   { display: inline-block; width: 7px; height: 7px; border-radius: 50%; vertical-align: middle; margin-right: 4px; }
.tdot-h { background: #10B981; }
.tdot-l { background: #F59E0B; }

/* ─── History Table ─── */
.hist-table-wrap { overflow-x: auto; }
.hist-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; color: #1A1A1A; }
.hist-table thead tr { background: #F9FAFB; }
.hist-table th {
    padding: 0.625rem 0.875rem; text-align: left; font-size: 0.6875rem; font-weight: 600;
    color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.07em;
    border-bottom: 1px solid #EBEBED; white-space: nowrap;
}
.hist-table td { padding: 0.75rem 0.875rem; border-bottom: 1px solid #F5F5F7; vertical-align: middle; white-space: nowrap; }
.hist-table tr:last-child td { border-bottom: none; }
.hist-row-hit td { background: #F0FDF4; }
.hist-row-miss td { background: #FEF2F2; }
.hist-row-pending td { background: #FAFAFB; }
.hit-badge { font-weight: 700; font-size: 0.9375rem; }
.hit-badge-win { color: #059669; }
.hit-badge-lose { color: #DC2626; }
.hit-badge-pending { color: #9CA3AF; font-weight: 500; font-size: 0.875rem; }

/* ─── Info / Warning / Success boxes ─── */
.ibox { background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 10px; padding: 0.875rem 1.125rem; font-size: 0.875rem; color: #0C4A6E; line-height: 1.65; margin-bottom: 0.75rem; }
.wbox { background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 10px; padding: 0.875rem 1.125rem; font-size: 0.875rem; color: #78350F; line-height: 1.65; margin-bottom: 0.75rem; }
.sbox { background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 0.875rem 1.125rem; font-size: 0.875rem; color: #14532D; line-height: 1.65; margin-bottom: 0.75rem; }

/* ─── Scenario cards ─── */
.sc   { border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; line-height: 1.7; }
.sc-h { background: #EEF2FF; border-left: 3px solid #4F46E5; }
.sc-t { background: #F0FDF4; border-left: 3px solid #059669; }
.sc-a { background: #FFFBEB; border-left: 3px solid #D97706; }
.sc-title { font-size: 0.8125rem; font-weight: 700; margin-bottom: 0.375rem; }
.sc-h .sc-title { color: #4F46E5; }
.sc-t .sc-title { color: #059669; }
.sc-a .sc-title { color: #92400E; }
.sc-body { font-size: 0.875rem; color: #374151; }

/* ─── Pace grid ─── */
.pg { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.5rem 0 0.75rem; }
.pi { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 6px; padding: 0.35rem 0.75rem; font-size: 0.8125rem; font-weight: 500; color: #374151; }

/* ─── Race story (phase-by-phase) ─── */
.story-grid { display: flex; gap: 1rem; flex-wrap: wrap; }
.story-phase { flex: 1; min-width: 220px; background: #F9FAFB; border: 1px solid #EBEBED; border-radius: 12px; padding: 1rem 1.125rem; }
.story-phase-title { font-size: 0.75rem; font-weight: 700; color: #4F46E5; margin-bottom: 0.5rem; }
.story-phase-body { font-size: 0.8125rem; color: #374151; line-height: 1.7; }
.sc-pattern { margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed rgba(0,0,0,0.08); font-size: 0.8125rem; color: #4B5563; }
.sc-pattern-label { font-weight: 600; color: #6B7280; margin-right: 0.25rem; }

/* ─── Section label ─── */
.sec-label { font-size: 0.6875rem; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.08em; margin: 1.5rem 0 0.75rem; }

/* ─── Metric Cards ─── */
.mc-row { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.mc {
    background: white; border-radius: 14px; padding: 1.375rem 1.625rem; flex: 1; min-width: 160px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px -4px rgba(0,0,0,0.07);
    border: 1px solid rgba(0,0,0,0.04);
}
.mc-label { font-size: 0.6875rem; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.625rem; }
.mc-value { font-size: 2.5rem; font-weight: 700; color: #1A1A1A; letter-spacing: -0.05em; line-height: 1; }
.mc-sub   { font-size: 0.6875rem; color: #B0B7C3; margin-top: 0.5rem; letter-spacing: 0.02em; }

/* ─── Widget overrides ─── */
button[data-baseweb="tab"] { font-size: 0.9375rem !important; font-weight: 500 !important; color: #6B7280 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #4F46E5 !important; font-weight: 600 !important; }
[data-baseweb="tab-highlight"] { background: #4F46E5 !important; }
[data-baseweb="tab-list"] { gap: 0.25rem !important; }

.stButton > button[kind="primary"] {
    background: #4F46E5 !important; color: white !important; border: none !important;
    border-radius: 9px !important; font-weight: 600 !important; font-size: 0.875rem !important;
    box-shadow: 0 1px 3px rgba(79,70,229,0.3) !important; transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4338CA !important; transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(79,70,229,0.4) !important;
}
.stButton > button[kind="secondary"] {
    background: white !important; color: #4F46E5 !important; border: 1.5px solid #C7D2FE !important;
    border-radius: 9px !important; font-weight: 600 !important; font-size: 0.875rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="secondary"]:hover { background: #EEF2FF !important; border-color: #A5B4FC !important; }

.stTextInput > div > div > input {
    border-radius: 9px !important; border: 1.5px solid #E5E7EB !important;
    font-size: 0.9375rem !important; background: white !important; color: #1A1A1A !important;
}
.stTextInput > div > div > input:focus {
    border-color: #4F46E5 !important; box-shadow: 0 0 0 3px rgba(79,70,229,0.12) !important;
}
.stTextInput > div > div > input::placeholder { color: #C4C9D4 !important; }

details {
    background: white !important; border-radius: 14px !important;
    border: 1px solid rgba(0,0,0,0.05) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    margin-bottom: 1.25rem !important; overflow: hidden !important;
}
details > summary {
    font-size: 0.9375rem !important; font-weight: 600 !important; color: #374151 !important;
    padding: 1rem 1.25rem !important; background: white !important;
    cursor: pointer !important; user-select: none !important;
}
details[open] > summary { border-bottom: 1px solid #F0F0F2 !important; }
details > div { padding: 1.125rem 1.25rem !important; }

.stSelectbox > div > div { border-radius: 9px !important; border: 1.5px solid #E5E7EB !important; background: white !important; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #A5B4FC, #4F46E5) !important; border-radius: 4px !important; }

[data-testid="stMetric"] { background: white; border-radius: 12px; padding: 1rem 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid rgba(0,0,0,0.04); }
[data-testid="stMetricLabel"] p { font-size: 0.6875rem !important; font-weight: 600 !important; color: #9CA3AF !important; text-transform: uppercase !important; letter-spacing: 0.06em !important; }
[data-testid="stMetricValue"]   { font-size: 1.875rem !important; font-weight: 700 !important; letter-spacing: -0.03em !important; }

h1 { font-size: 2.125rem !important; font-weight: 800 !important; letter-spacing: -0.03em !important; }
h2 { font-size: 1.5rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; margin-top: 1.5rem !important; }
h3 { font-size: 1.1875rem !important; font-weight: 600 !important; }
hr { border-color: #EBEBED !important; margin: 1.75rem 0 !important; }
.stCaption p   { font-size: 0.8125rem !important; color: #9CA3AF !important; }
.stAlert       { border-radius: 12px !important; }
.stDataFrame   { border-radius: 12px !important; overflow: hidden !important; }
.stCheckbox label { font-size: 0.875rem !important; color: #374151 !important; }
</style>
""", unsafe_allow_html=True)


# ===================================================
# モデル読み込み（起動時1回だけ）
# ===================================================
@st.cache_resource
def load_feature_builder():
    return FeatureBuilder(MODEL_DIR)


@st.cache_resource
def load_predictor():
    return Predictor(MODEL_DIR)


# ===================================================
# 記録・照合
# ===================================================
def save_prediction(race_id, race_info, result):
    rows = []
    for i, row in result.iterrows():
        rows.append({
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "race_id": race_id,
            "race_name": race_info.get("race_name", ""),
            "venue": race_info.get("venue", ""),
            "course_type": race_info.get("course_type", ""),
            "distance": race_info.get("distance", ""),
            "pred_rank": i + 1,
            "number": int(row["number_num"]) if pd.notna(row.get("number_num")) else None,
            "horse_name": row["horse_name"],
            "win_prob": round(float(row["win_prob"]), 4),
            "odds": round(float(row["odds"]), 1) if pd.notna(row.get("odds")) else None,
            "popularity": int(row["popularity"]) if pd.notna(row.get("popularity")) else None,
            "main_style": row.get("main_style"),
            "data_available": bool(row.get("data_available", False)),
            "actual_rank": None,
            "hit": None,
            "user_pick_number": None,
            "user_pick_name": None,
        })
    new_df = pd.DataFrame(rows)
    if os.path.exists(HISTORY_CSV):
        existing = pd.read_csv(HISTORY_CSV)
        existing = existing[existing["race_id"].astype(str) != str(race_id)]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_csv(HISTORY_CSV, index=False)


def save_user_prediction(race_id, user_pick_number, user_pick_name):
    if not os.path.exists(HISTORY_CSV):
        return False
    df = pd.read_csv(HISTORY_CSV)
    mask = df["race_id"].astype(str) == str(race_id)
    if not mask.any():
        return False
    df.loc[mask, "user_pick_number"] = user_pick_number
    df.loc[mask, "user_pick_name"] = user_pick_name
    df.to_csv(HISTORY_CSV, index=False)
    return True


def update_results():
    if not os.path.exists(HISTORY_CSV):
        return False, "予想の記録がありません。"
    df = pd.read_csv(HISTORY_CSV)
    need_update = df["actual_rank"].isna()
    if not need_update.any():
        return True, "照合が必要なレースはありません（すべて照合済みです）。"
    target_race_ids = df.loc[need_update, "race_id"].unique()
    updated_races = 0
    failed_races = []
    for race_id in target_race_ids:
        race_id_str = str(race_id)
        race_mask = df["race_id"].astype(str) == race_id_str
        rows_to_update = df.index[race_mask & need_update]
        any_fetched = False
        for idx in rows_to_update:
            umaban = df.at[idx, "number"]
            if pd.isna(umaban):
                continue
            rank = _fetch_result_rank(race_id_str, int(umaban))
            if rank is not None:
                df.at[idx, "actual_rank"] = rank
                any_fetched = True
        if any_fetched:
            honmei_idx = df.index[race_mask & (df["pred_rank"] == 1)]
            for idx in honmei_idx:
                actual = df.at[idx, "actual_rank"]
                if pd.notna(actual):
                    df.at[idx, "hit"] = bool(int(actual) == 1)
            updated_races += 1
        else:
            failed_races.append(race_id_str)
    df.to_csv(HISTORY_CSV, index=False)
    if updated_races == 0:
        return False, "結果を取得できませんでした（レースが未確定か、通信エラーの可能性があります）。"
    if failed_races:
        return True, (
            f"{updated_races} レースを更新しました。"
            f"{len(failed_races)} レースは結果未確定または取得失敗でした。"
        )
    return True, f"{updated_races} レースの結果を照合しました。"


# ===================================================
# 汎用ヘルパー
# ===================================================
def _safe_str(val, fmt=None):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-"
    return fmt.format(val) if fmt else str(val)


def _e(s):
    return _html_mod.escape(str(s)) if s is not None else ""


def _pace_comment(style_counts, n_horses):
    nige = style_counts.get("逃げ", 0)
    senko = style_counts.get("先行", 0)
    front = nige + senko
    if nige >= 3:
        return "ハイペース濃厚（逃げ馬多数）→ 差し・追込有利"
    if nige == 0:
        return "スローペース濃厚（逃げ馬不在）→ 前残り有利"
    if front >= n_horses * 0.5:
        return "前々の展開（先行勢多数）→ 力のある先行馬有利"
    return "平均的なペース想定"


# ===================================================
# HTML レンダリングヘルパー
# ===================================================
def _style_badge_html(style):
    cls_map = {"逃げ": "sb-nige", "先行": "sb-senkou", "差し": "sb-sashi", "追込": "sb-oikomi"}
    style_str = str(style) if (style and pd.notna(style)) else "?"
    cls = cls_map.get(style_str, "sb-other")
    return f'<span class="sb {cls}">{_e(style_str)}</span>'


def _mark_html(mark):
    if not mark:
        return ""
    parts = []
    if "◎" in mark:
        parts.append('<span class="mk mk-h">◎</span>')
    if "○" in mark:
        parts.append('<span class="mk mk-t">○</span>')
    if "▲" in mark:
        parts.append('<span class="mk mk-s">▲</span>')
    if "★" in mark:
        parts.append('<span class="mk mk-a">★</span>')
    return "".join(parts)


def _render_race_header(race_info, n_horses):
    race_name = _e(race_info.get("race_name") or "レース")
    venue     = _e(race_info.get("venue") or "")
    course    = _e(race_info.get("course_type") or "")
    dist      = race_info.get("distance") or ""
    weather   = _e(race_info.get("weather") or "-")
    track     = _e(race_info.get("track_condition") or "-")
    course_str = f"{course}{dist}m" if dist else (course or "-")
    st.markdown(f"""
    <div class="race-header-card">
      <p class="race-venue-label">{venue}</p>
      <p class="race-name">{race_name}</p>
      <div class="race-meta">
        <span class="race-meta-item">🏟 {venue}</span>
        <span class="race-meta-item">🏇 {course_str}</span>
        <span class="race-meta-item">🌤 天気 {weather}</span>
        <span class="race-meta-item">🌿 馬場 {track}</span>
        <span class="race-meta-item">👥 {n_horses}頭立て</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_honmei_card(best):
    best_num  = _safe_str(best.get("number_num"), "{:.0f}")
    best_odds = _safe_str(best.get("odds"), "{:.1f}")
    best_prob = f"{best['win_prob']:.1%}"
    best_pop  = _safe_str(best.get("popularity"), "{:.0f}")
    st.markdown(f"""
    <div class="honmei-card">
      <div class="honmei-mark">◎</div>
      <div>
        <div class="honmei-label-text">本命馬</div>
        <div class="honmei-horse-name">{best_num}番　{_e(best['horse_name'])}</div>
        <div class="honmei-stats">
          <span class="stat-primary">1着確率　{best_prob}</span>
          <span class="stat-muted">オッズ　{best_odds}倍</span>
          <span class="stat-muted">{best_pop}番人気</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_pred_table(result, ana_horse_set):
    MARK_MAP = {1: "◎", 2: "○", 3: "▲"}
    max_prob = result["win_prob"].max() if len(result) > 0 else 1.0

    rows_html = ""
    for i, row in result.iterrows():
        rank = i + 1
        mark = MARK_MAP.get(rank, "")
        if i in ana_horse_set:
            mark = mark + "★" if mark else "★"

        row_class = "hr-row" if rank == 1 else ""
        mark_html = _mark_html(mark)
        style_html = _style_badge_html(row.get("main_style"))

        prob_val = float(row["win_prob"])
        bar_pct  = int((prob_val / max_prob) * 100) if max_prob > 0 else 0
        prob_str = f"{prob_val:.1%}"

        trust      = "○" if row.get("data_available") else "△"
        trust_cls  = "tdot-h" if trust == "○" else "tdot-l"
        trust_label = "過去成績あり" if trust == "○" else "データ少"

        horse_name = _e(row["horse_name"])
        if rank == 1:
            horse_name = f"<strong>{horse_name}</strong>"

        num_str  = _safe_str(row.get("number_num"), "{:.0f}")
        odds_str = _safe_str(row.get("odds"), "{:.1f}")
        pop_str  = _safe_str(row.get("popularity"), "{:.0f}")

        rows_html += f"""
        <tr class="{row_class}">
          <td>{mark_html}</td>
          <td style="color:#9CA3AF;font-size:0.8125rem">{rank}</td>
          <td style="font-weight:600">{num_str}</td>
          <td>{horse_name}</td>
          <td>{style_html}</td>
          <td>
            <div class="prob-cell">
              <span class="prob-text">{prob_str}</span>
              <div class="prob-track"><div class="prob-fill" style="width:{bar_pct}%"></div></div>
            </div>
          </td>
          <td style="color:#374151">{odds_str}</td>
          <td style="color:#374151">{pop_str}</td>
          <td><span class="tdot {trust_cls}"></span><span style="font-size:0.75rem;color:#9CA3AF">{trust_label}</span></td>
        </tr>"""

    st.markdown(f"""
    <div class="card pred-table-wrap">
      <div class="card-label">予測ランキング</div>
      <table class="pred-table">
        <thead>
          <tr>
            <th>印</th><th>順位</th><th>馬番</th><th>馬名</th><th>脚質</th>
            <th>1着確率</th><th>オッズ</th><th>人気</th><th>信頼</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="margin-top:0.875rem;font-size:0.6875rem;color:#9CA3AF">
        ◎本命　○対抗　▲単穴　★穴狙い候補　／　信頼：● 過去成績あり　● 過去成績少（精度低め）
      </p>
    </div>""", unsafe_allow_html=True)


def _render_pace_section(result):
    style_counts = result["main_style"].dropna().value_counts().to_dict()
    parts = [
        f"{s}：{style_counts[s]}頭"
        for s in ["逃げ", "先行", "差し", "追込"]
        if style_counts.get(s, 0) > 0
    ]
    pace = _pace_comment(style_counts, len(result))
    nige_df = result[result["main_style"] == "逃げ"]
    nige_names = [
        f"{int(r['number_num'])}番 {_e(r['horse_name'])}"
        for _, r in nige_df.iterrows()
        if pd.notna(r["number_num"])
    ]
    items_html = "".join(f'<span class="pi">{p}</span>' for p in (parts or ["データなし"]))
    nige_html = (
        f'<p style="font-size:0.875rem;color:#374151;margin-top:0.75rem;margin-bottom:0">'
        f'🏇 逃げ予想：<strong>{" / ".join(nige_names)}</strong></p>'
    ) if nige_names else ""
    body = f'<div class="pg">{items_html}</div><div class="ibox">⚡ 想定ペース：{_e(pace)}</div>{nige_html}'
    st.markdown(
        f'<div class="card"><div class="card-label">展開予想</div>{body}</div>',
        unsafe_allow_html=True,
    )


def _render_story_section(story):
    if not any(story.values()):
        return
    phases = [
        ("スタート〜序盤", story.get("start", "")),
        ("前半〜中盤", story.get("middle", "")),
        ("直線", story.get("stretch", "")),
    ]
    phases_html = "".join(
        f'<div class="story-phase"><div class="story-phase-title">▼ {_e(title)}</div>'
        f'<div class="story-phase-body">{_e(text)}</div></div>'
        for title, text in phases
    )
    st.markdown(
        f'<div class="card"><div class="card-label">フェーズ別展開ストーリー</div>'
        f'<div class="story-grid">{phases_html}</div></div>',
        unsafe_allow_html=True,
    )


def _render_scenario_section(scenarios, pace_info, story=None, pattern_db=None):
    role_defs = [
        ("◎ 本命", "本命", "sc-h"),
        ("○ 対抗", "対抗", "sc-t"),
        ("★ 穴",  "穴",  "sc-a"),
    ]
    show_pattern = bool(story) and any(story.values())
    cards_html = ""
    for label, role, css_cls in role_defs:
        horse = scenarios[role]
        if horse is None:
            if role == "穴":
                cards_html += '<p style="font-size:0.875rem;color:#9CA3AF;margin:0">このレースに穴狙い対象の馬はいません。</p>'
            continue
        try:
            num_str = f"{int(horse['number_num'])}番"
        except (TypeError, ValueError):
            num_str = ""
        comment = generate_scenario_comment(horse, role, pace_info)
        title = f"{_e(label)}：{num_str}　{_e(horse['horse_name'])}"
        body  = _e(comment)
        pattern_html = ""
        if show_pattern:
            pattern_comment = generate_pattern_comment(horse, role, story, pattern_db)
            pattern_html = (
                f'<div class="sc-pattern"><span class="sc-pattern-label">立ち回り×展開</span>'
                f'{_e(pattern_comment)}</div>'
            )
        cards_html += f'<div class="sc {css_cls}"><div class="sc-title">{title}</div><div class="sc-body">{body}</div>{pattern_html}</div>'
    st.markdown(
        f'<div class="card"><div class="card-label">予想シナリオ</div>{cards_html}</div>',
        unsafe_allow_html=True,
    )


def _render_ana_section(ana_pick):
    if len(ana_pick) == 0:
        ana_html = '<p style="font-size:0.875rem;color:#9CA3AF;margin:0">このレースに穴狙い対象の馬はいません。</p>'
    else:
        ana_html = ""
        for _, row in ana_pick.iterrows():
            pop    = int(row["popularity_num"])
            odds_d = _safe_str(row.get("odds"), "{:.1f}倍")
            if pop >= 10:
                rec = "推奨：複勝が手堅め（検証回収率109% / 的中率9%）<br>単勝は一発狙い（検証回収率152% / 的中率2%）"
            else:
                rec = "推奨：単勝が狙い目（検証回収率132% / 的中率5%）<br>複勝なら当たりやすい（検証回収率93% / 的中率18%）"
            inner = (
                f'<strong>★ {int(row["number_num"])}番　{_e(row["horse_name"])}</strong>'
                f'　{pop}番人気 / {_e(odds_d)}<br>'
                f'<span style="display:block;margin-top:0.5rem;color:#92400E">実力評価は高いが、市場で過小評価されている可能性があります。</span>'
                f'<span style="display:block;margin-top:0.375rem">{rec}</span>'
            )
            ana_html += f'<div class="wbox">{inner}</div>'
    st.markdown(
        f'<div class="card"><div class="card-label">穴狙い（実験的機能）</div>{ana_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "※ 上記は2023〜2025年の過去検証値です。連敗が続く前提の長期戦略であり、"
        "利益を保証するものではありません。趣味・実験用に少額での利用を推奨します。"
    )


def _render_horse_reason(horse, result):
    if not horse.get("data_available", False):
        st.caption("※ 過去成績データ不足のため、一部は平均値で補完されています。")

    def _avg(col):
        return result[col].mean() if col in result.columns else None

    c1, c2, c3 = st.columns(3)
    wr = float(horse.get("horse_winrate_safe") or 0)
    wr_avg = _avg("horse_winrate_safe") or 0
    c1.metric("馬の通算勝率", f"{wr:.1%}", f"{wr - wr_avg:+.1%} vs 平均")

    jr = float(horse.get("jockey_winrate_safe") or 0)
    jr_avg = _avg("jockey_winrate_safe") or 0
    c2.metric("騎手勝率", f"{jr:.1%}", f"{jr - jr_avg:+.1%} vs 平均")

    top3 = float(horse.get("horse_top3rate_safe") or 0)
    top3_avg = _avg("horse_top3rate_safe") or 0
    c3.metric("複勝率", f"{top3:.1%}", f"{top3 - top3_avg:+.1%} vs 平均")

    c4, c5, c6 = st.columns(3)
    last3f = horse.get("horse_avg_last3f_safe")
    last3f_avg = _avg("horse_avg_last3f_safe")
    if last3f and pd.notna(last3f) and float(last3f) > 0 and last3f_avg:
        c4.metric("平均上がり3F", f"{float(last3f):.1f}秒", f"{last3f_avg - float(last3f):+.1f}秒 vs 平均")
    else:
        c4.metric("平均上がり3F", "-")

    prev_rank_val = horse.get("prev_rank")
    pr_avg = _avg("prev_rank")
    if prev_rank_val is not None and pd.notna(prev_rank_val) and float(prev_rank_val) > 0:
        pr = float(prev_rank_val)
        delta_pr = (pr_avg - pr) if pr_avg else 0
        c5.metric("前走着順", f"{pr:.0f}着", f"{delta_pr:+.1f} vs 平均")
    else:
        c5.metric("前走着順", "-")

    pl3f = horse.get("prev_last3f")
    pl3f_avg = _avg("prev_last3f")
    if pl3f is not None and pd.notna(pl3f) and float(pl3f) > 0 and pl3f_avg:
        pl3f = float(pl3f)
        c6.metric("前走上がり3F", f"{pl3f:.1f}秒", f"{pl3f_avg - pl3f:+.1f}秒 vs 平均")
    else:
        c6.metric("前走上がり3F", "-")


# ===================================================
# ページ：レース予想
# ===================================================
def page_predict():
    if "pred_result" not in st.session_state:
        st.session_state.pred_result    = None
        st.session_state.pred_race_id   = None
        st.session_state.pred_race_info = None

    col_input, col_btn, _col_spacer = st.columns([2, 1, 4])
    with col_input:
        race_id = st.text_input(
            "race_id",
            placeholder="例: 202506010811",
            label_visibility="collapsed",
        )
    with col_btn:
        run = st.button("予想する", type="primary", use_container_width=True)

    if run:
        if not race_id:
            st.error("race_id を入力してください。")
        else:
            try:
                builder   = load_feature_builder()
                predictor = load_predictor()

                with st.spinner("出馬表を取得中…"):
                    df_raw, race_info = get_shutuba(race_id)

                with st.spinner("オッズを取得中…"):
                    df_raw = merge_odds(df_raw, race_id)
                    df_raw["entry_count"] = len(df_raw)

                with st.spinner("前走情報を取得中…（時間がかかります）"):
                    _prev_bar  = st.progress(0)
                    _prev_text = st.empty()

                    def _prev_cb(current, total):
                        _prev_bar.progress(current / total)
                        _prev_text.text(f"前走情報取得中... {current}/{total}頭")

                    df_raw = merge_prev_race_info(df_raw, progress_callback=_prev_cb)
                    _prev_bar.empty()
                    _prev_text.empty()

                with st.spinner("過去成績を照合・特徴量構築中…"):
                    df_feat = builder.build(df_raw)

                with st.spinner("予測中…"):
                    result = predictor.predict(df_feat)

                save_prediction(race_id, race_info, result)
                st.session_state.pred_result    = result
                st.session_state.pred_race_id   = race_id
                st.session_state.pred_race_info = race_info

            except ValueError as e:
                st.error(f"データ取得エラー: {e}\n\nrace_id が正しいか確認してください。")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    result    = st.session_state.pred_result
    race_info = st.session_state.pred_race_info
    race_id   = st.session_state.pred_race_id

    if result is None:
        st.markdown("""
        <div style="text-align:center;padding:4rem 0;color:#9CA3AF">
          <div style="font-size:2.5rem;margin-bottom:0.875rem">🐎</div>
          <div style="font-size:0.9375rem;font-weight:500;color:#6B7280">race_id（12桁）を入力して「予想する」を押してください</div>
          <div style="font-size:0.8125rem;margin-top:0.5rem;color:#B0B7C3">例：202506010811　→　2025年 東京競馬場 第1回 第8日 第11レース</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # レース情報カード
    _render_race_header(race_info, len(result))

    # 穴狙い候補を事前計算（テーブル印に使用）
    ana_horse_set = set()
    if "ana_rank" in result.columns:
        res2 = result.copy()
        res2["popularity_num"] = pd.to_numeric(res2["popularity"], errors="coerce")
        ana_pick = res2[(res2["ana_rank"] == 1) & (res2["popularity_num"] >= 7)]
        ana_horse_set = set(ana_pick.index)
    else:
        ana_pick = pd.DataFrame()

    # 本命馬カード
    _render_honmei_card(result.iloc[0])

    # 予測テーブル
    _render_pred_table(result, ana_horse_set)

    # 展開予想カード
    if "main_style" in result.columns:
        _render_pace_section(result)

    # フェーズ別展開ストーリーカード
    builder = load_feature_builder()
    story = generate_race_story(result, builder.pattern_db)
    _render_story_section(story)

    # 予想シナリオカード
    pace_info = build_pace_info(result)
    scenarios = select_scenario_horses(result)
    _render_scenario_section(scenarios, pace_info, story, builder.pattern_db)

    # 予測根拠（エキスパンダーのまま：Streamlitウィジェットを含む）
    with st.expander("🔍 予測根拠（上位馬のファクター内訳）", expanded=False):
        st.caption("各指標の「vs 平均」はこのレースの出走馬全体との比較です。上がりは小さいほど速い（良い）。")
        for label, role in [("◎ 本命", "本命"), ("○ 対抗", "対抗")]:
            horse = scenarios[role]
            if horse is None:
                continue
            try:
                num_str = f"{int(horse['number_num'])}番"
            except (TypeError, ValueError):
                num_str = ""
            st.markdown(f"**{label}：{num_str} {horse['horse_name']}**")
            _render_horse_reason(horse, result)
            st.divider()

    # 穴狙いカード
    if "ana_rank" in result.columns:
        _render_ana_section(ana_pick)

    st.caption(
        "⚠️ この予測は機械学習モデルによるものです。的中を保証するものではありません。"
        "馬券は自己責任でお楽しみください。"
    )

    # ユーザー予想記録
    st.divider()
    st.markdown('<div class="sec-label">あなたの予想を記録する</div>', unsafe_allow_html=True)

    horse_list = result.sort_values("number_num").dropna(subset=["number_num"])
    horse_options = [
        f"{int(r['number_num'])}番 {r['horse_name']}"
        for _, r in horse_list.iterrows()
    ]

    default_idx = 0
    if os.path.exists(HISTORY_CSV):
        hist = pd.read_csv(HISTORY_CSV)
        prev = hist[hist["race_id"].astype(str) == str(race_id)]
        if "user_pick_number" in prev.columns and prev["user_pick_number"].notna().any():
            prev_num  = int(prev["user_pick_number"].dropna().iloc[0])
            prev_name = prev["user_pick_name"].dropna().iloc[0]
            prev_label = f"{prev_num}番 {prev_name}"
            if prev_label in horse_options:
                default_idx = horse_options.index(prev_label)

    col_pick, col_save = st.columns([4, 1])
    with col_pick:
        user_pick = st.selectbox(
            "本命馬を選んでください",
            horse_options,
            index=default_idx,
            label_visibility="collapsed",
        )
    with col_save:
        if st.button("記録する", type="secondary", use_container_width=True):
            pick_num  = int(user_pick.split("番")[0])
            pick_name = user_pick.split("番 ", 1)[1]
            if save_user_prediction(race_id, pick_num, pick_name):
                st.success(f"記録しました: {user_pick}")
            else:
                st.warning("先に「予想する」を実行してください。")


# ===================================================
# 成績確認：集計ヘルパー
# ===================================================
def _norm_hit(v):
    if pd.isna(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "〇", "○"):
        return True
    if s in ("false", "0", "×", "x"):
        return False
    return None


def _pop_bucket(pop):
    if pd.isna(pop):
        return None
    p = int(pop)
    if p == 1:
        return "1番人気"
    if p in (2, 3):
        return "2-3番人気"
    if p in (4, 5, 6):
        return "4-6番人気"
    return "7番人気以下"


def _hit_rate_and_recovery(sub):
    n = len(sub)
    if n == 0:
        return None, None
    hit_rate = sub["hit_bool"].mean()
    hit_rows = sub[sub["hit_bool"] == True]
    total_return = hit_rows["odds"].fillna(0).sum() * 100
    total_stake = n * 100
    recovery = total_return / total_stake if total_stake > 0 else None
    return hit_rate, recovery


def _render_summary_cards(n_races, matched_df):
    n_matched = len(matched_df)
    if n_matched == 0:
        hit_rate_str, recover_str = "照合待ち", "照合待ち"
    else:
        hit_rate, recovery = _hit_rate_and_recovery(matched_df)
        hit_rate_str = f"{hit_rate:.1%}"
        recover_str = f"{recovery:.0%}" if recovery is not None else "—"

    st.markdown(f"""
    <div class="mc-row">
      <div class="mc">
        <div class="mc-label">予想レース数</div>
        <div class="mc-value">{n_races}</div>
        <div class="mc-sub">races predicted</div>
      </div>
      <div class="mc">
        <div class="mc-label">的中率</div>
        <div class="mc-value" style="font-size:{'1.5rem' if n_matched == 0 else '2.5rem'}">{hit_rate_str}</div>
        <div class="mc-sub">{n_matched}件照合済み</div>
      </div>
      <div class="mc">
        <div class="mc-label">回収率</div>
        <div class="mc-value" style="font-size:{'1.5rem' if n_matched == 0 else '2.5rem'}">{recover_str}</div>
        <div class="mc-sub">return rate</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_history_charts(matched_df):
    with st.expander("📊 詳細グラフを見る", expanded=False):
        # ① 月別的中率
        monthly = matched_df.copy()
        monthly["year_month"] = pd.to_datetime(monthly["saved_at"]).dt.strftime("%Y-%m")
        monthly_rate = monthly.groupby("year_month")["hit_bool"].mean().sort_index()
        fig1 = go.Figure(go.Scatter(
            x=monthly_rate.index, y=monthly_rate.values,
            mode="lines+markers", line=dict(color="#4F46E5", width=3),
            marker=dict(size=8, color="#4F46E5"),
        ))
        fig1.update_layout(
            title="月別的中率", yaxis=dict(tickformat=".0%", range=[0, 1]),
            height=320, margin=dict(t=50, b=30, l=30, r=20),
            template="simple_white",
        )
        st.plotly_chart(fig1, use_container_width=True)

        # ② 人気帯別的中率
        pop_df = matched_df.copy()
        pop_df["bucket"] = pop_df["popularity"].apply(_pop_bucket)
        order = ["1番人気", "2-3番人気", "4-6番人気", "7番人気以下"]
        bucket_rate = pop_df.dropna(subset=["bucket"]).groupby("bucket")["hit_bool"].mean()
        bucket_rate = bucket_rate.reindex(order).dropna()
        fig2 = go.Figure(go.Bar(
            x=bucket_rate.index, y=bucket_rate.values,
            marker_color="#4F46E5",
        ))
        fig2.update_layout(
            title="人気帯別的中率", yaxis=dict(tickformat=".0%", range=[0, 1]),
            height=320, margin=dict(t=50, b=30, l=30, r=20),
            template="simple_white",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # ③ 本命 vs 穴狙い
        honmei_grp = matched_df[matched_df["popularity"].between(1, 3)]
        ana_grp = matched_df[matched_df["popularity"] >= 7]
        h_rate, h_rec = _hit_rate_and_recovery(honmei_grp)
        a_rate, a_rec = _hit_rate_and_recovery(ana_grp)

        c1, c2 = st.columns(2)
        with c1:
            fig3 = go.Figure(go.Bar(
                x=["本命 (1-3番人気)", "穴狙い (7番人気以下)"],
                y=[h_rate or 0, a_rate or 0],
                marker_color=["#4F46E5", "#D97706"],
            ))
            fig3.update_layout(
                title="的中率 比較", yaxis=dict(tickformat=".0%"),
                height=300, margin=dict(t=50, b=30, l=30, r=20),
                template="simple_white",
            )
            st.plotly_chart(fig3, use_container_width=True)
        with c2:
            fig4 = go.Figure(go.Bar(
                x=["本命 (1-3番人気)", "穴狙い (7番人気以下)"],
                y=[h_rec or 0, a_rec or 0],
                marker_color=["#4F46E5", "#D97706"],
            ))
            fig4.update_layout(
                title="回収率 比較", yaxis=dict(tickformat=".0%"),
                height=300, margin=dict(t=50, b=30, l=30, r=20),
                template="simple_white",
            )
            st.plotly_chart(fig4, use_container_width=True)


def _render_history_table(honmei_df):
    view = honmei_df.sort_values("saved_at", ascending=False)
    rows_html = ""
    for _, row in view.iterrows():
        hit = row["hit_bool"]
        if hit is True:
            row_cls = "hist-row-hit"
            hit_html = '<span class="hit-badge hit-badge-win">〇</span>'
            actual_str = _safe_str(row.get("actual_rank"), "{:.0f}着")
        elif hit is False:
            row_cls = "hist-row-miss"
            hit_html = '<span class="hit-badge hit-badge-lose">×</span>'
            actual_str = _safe_str(row.get("actual_rank"), "{:.0f}着")
        else:
            row_cls = "hist-row-pending"
            hit_html = '<span class="hit-badge-pending">⏳</span>'
            actual_str = "⏳"

        race_name = row.get("race_name")
        venue = row.get("venue")
        race_name_s = _e(race_name) if pd.notna(race_name) and str(race_name).strip() else "-"
        venue_s = _e(venue) if pd.notna(venue) and str(venue).strip() else "-"

        pop_str = _safe_str(row.get("popularity"), "{:.0f}")
        odds_str = _safe_str(row.get("odds"), "{:.1f}")
        prob_str = f"{float(row['win_prob']):.1%}" if pd.notna(row.get("win_prob")) else "-"
        style_html = _style_badge_html(row.get("main_style"))

        rows_html += f"""
        <tr class="{row_cls}">
          <td style="color:#6B7280;font-size:0.8125rem">{_e(row.get('saved_at'))}</td>
          <td>{race_name_s}（{venue_s}）</td>
          <td style="font-weight:600">{_e(row['horse_name'])}</td>
          <td>{pop_str}</td>
          <td>{odds_str}</td>
          <td>{prob_str}</td>
          <td>{style_html}</td>
          <td>{actual_str}</td>
          <td>{hit_html}</td>
        </tr>"""

    st.markdown(f"""
    <div class="card hist-table-wrap">
      <table class="hist-table">
        <thead>
          <tr>
            <th>日時</th><th>レース名（会場）</th><th>本命馬名</th><th>人気</th>
            <th>オッズ</th><th>1着確率</th><th>脚質</th><th>実着順</th><th>的中</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>""", unsafe_allow_html=True)


# ===================================================
# ページ：成績確認
# ===================================================
def page_history():
    if not os.path.exists(HISTORY_CSV):
        st.markdown("""
        <div style="text-align:center;padding:4rem 0;color:#9CA3AF">
          <div style="font-size:2.5rem;margin-bottom:0.875rem">🏇</div>
          <div style="font-size:0.9375rem;font-weight:500;color:#6B7280">まだ予想記録がありません</div>
          <div style="font-size:0.8125rem;margin-top:0.5rem;color:#B0B7C3">レース予想ページで予想を実行すると自動で記録されます</div>
        </div>
        """, unsafe_allow_html=True)
        return

    df = pd.read_csv(HISTORY_CSV)
    if len(df) == 0:
        st.markdown("""
        <div style="text-align:center;padding:4rem 0;color:#9CA3AF">
          <div style="font-size:2.5rem;margin-bottom:0.875rem">🏇</div>
          <div style="font-size:0.9375rem;font-weight:500;color:#6B7280">まだ予想記録がありません</div>
          <div style="font-size:0.8125rem;margin-top:0.5rem;color:#B0B7C3">レース予想ページで予想を実行すると自動で記録されます</div>
        </div>
        """, unsafe_allow_html=True)
        return

    n_races   = df["race_id"].nunique()
    honmei_df = df[df["pred_rank"] == 1].copy()
    honmei_df["hit_bool"] = honmei_df["hit"].apply(_norm_hit)
    matched_df = honmei_df[honmei_df["hit_bool"].notna()]

    # サマリーカード
    _render_summary_cards(n_races, matched_df)

    # 詳細グラフ（照合済みが5件以上のときのみ）
    if len(matched_df) >= 5:
        _render_history_charts(matched_df)

    # 記録一覧
    st.markdown('<div class="sec-label">予想記録一覧</div>', unsafe_allow_html=True)

    col_btn, _ = st.columns([2, 5])
    with col_btn:
        if st.button("結果を照合する", type="primary", use_container_width=True):
            with st.spinner("照合中…"):
                ok, msg = update_results()
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)
    st.caption("照合すると実際の着順と的中が自動で判定されます")

    show_all = st.checkbox("全出走馬を表示（チェックなし：本命馬のみ）")
    if show_all:
        view = df.copy()
        for col in ["race_name", "venue", "popularity", "actual_rank", "hit"]:
            if col in view.columns:
                view[col] = view[col].apply(lambda v: "-" if pd.isna(v) else v)
        col_map = {
            "saved_at": "保存日時", "race_id": "レースID", "race_name": "レース名",
            "venue": "会場", "course_type": "コース", "distance": "距離(m)",
            "pred_rank": "予想順位", "number": "馬番", "horse_name": "馬名",
            "win_prob": "1着確率", "odds": "オッズ", "popularity": "人気",
            "main_style": "脚質", "actual_rank": "実着順", "hit": "的中",
            "user_pick_number": "自分の予想(馬番)", "user_pick_name": "自分の予想(馬名)",
        }
        view = view.rename(columns=col_map)
        show_cols = [v for v in col_map.values() if v in view.columns]
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)
    else:
        _render_history_table(honmei_df)


# ===================================================
# メインアプリ
# ===================================================
NAV_PAGES = ["レース予想", "成績確認"]


def _render_sidebar():
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = NAV_PAGES[0]

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand">
          <div class="sidebar-brand-icon">🏇</div>
          <div class="sidebar-brand-title">競馬AI予測</div>
        </div>
        """, unsafe_allow_html=True)

        for label in NAV_PAGES:
            is_active = st.session_state.nav_page == label
            if st.button(
                label,
                key=f"nav_{label}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state.nav_page = label
                st.rerun()

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
        st.caption("LightGBM × MLによる競馬予測")
        st.caption("モデル: LightGBM / データ: 2010-2025年")


def _render_hero():
    st.markdown("""
    <div class="hero-header">
      <div class="hero-title">競馬AI予測</div>
      <div class="hero-tagline">AIが導く、次の一手。</div>
    </div>
    <hr class="hero-divider">
    """, unsafe_allow_html=True)


def main():
    _render_sidebar()
    _render_hero()

    if st.session_state.nav_page == "レース予想":
        page_predict()
    else:
        page_history()


main()
