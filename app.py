"""
競馬単勝予測アプリ（Streamlit）
学習済みLightGBMモデルでレースの1着確率を予測する
"""
import streamlit as st
import pandas as pd
import pickle

# ===== ページ設定 =====
st.set_page_config(
    page_title="競馬AI予測",
    page_icon="🐎",
    layout="wide",
)

# ===== モデル・データ読み込み（キャッシュで高速化） =====
@st.cache_resource
def load_model():
    with open('model/model_v4.pkl', 'rb') as f:
        model = pickle.load(f)
    with open('model/features_v4.pkl', 'rb') as f:
        features = pickle.load(f)
    return model, features

@st.cache_data
def load_data():
    df = pd.read_parquet('model/race_data.parquet')
    return df

model, features = load_model()
df = load_data()

# ===== 予測関数 =====
def predict_race(race_id):
    race_data = df[df['race_id'] == race_id].copy()
    if len(race_data) == 0:
        return None, None

    X_race = race_data[features].copy()
    X_race['odds'] = pd.to_numeric(X_race['odds'], errors='coerce')
    valid_mask = X_race.notna().all(axis=1)
    X_race_valid = X_race[valid_mask]
    if len(X_race_valid) == 0:
        return None, None

    proba = model.predict_proba(X_race_valid)[:, 1]
    result = race_data[valid_mask][['number', 'horse_name', 'odds', 'rank']].copy()
    result['win_prob'] = proba
    result['odds'] = pd.to_numeric(result['odds'], errors='coerce')
    result['expected_value'] = result['win_prob'] * result['odds']
    result = result.sort_values('win_prob', ascending=False).reset_index(drop=True)

    return result, race_data.iloc[0]

# ===== UI =====
st.title("🐎 競馬AI単勝予測")
st.caption("学習済みLightGBMモデルによる1着確率の予測ツール")

# サイドバー：レース選択
st.sidebar.header("レースを選ぶ")

# 会場で絞り込み
venues = sorted(df['venue'].dropna().unique())
selected_venue = st.sidebar.selectbox("会場", venues)

# 選択した会場のレース一覧
venue_races = df[df['venue'] == selected_venue]['race_id'].unique()
selected_race = st.sidebar.selectbox("レースID", sorted(venue_races))

# 予測実行
if st.sidebar.button("予測する", type="primary"):
    result, info = predict_race(selected_race)

    if result is None:
        st.error("このレースは予測できません（データ欠損）")
    else:
        # レース情報
        st.subheader(f"{info['venue']} {info['course_type']}{info['distance']}m")
        col1, col2, col3 = st.columns(3)
        col1.metric("天気", info['weather'])
        col2.metric("馬場", info['track_condition'])
        col3.metric("出走頭数", f"{len(result)}頭")

        # 本命馬
        best = result.iloc[0]
        st.success(f"🎯 本命: {best['number']}番 {best['horse_name']}（1着確率 {best['win_prob']:.1%}）")

        # 予測テーブル
        st.subheader("予測ランキング")
        display = result.copy()
        display['win_prob'] = (display['win_prob'] * 100).round(1)
        display['expected_value'] = display['expected_value'].round(2)
        display['買い目'] = display.apply(
            lambda r: '◎' if r['expected_value'] >= 1.0 and r['win_prob'] >= 15 else '', axis=1
        )
        display = display.rename(columns={
            'number': '馬番', 'horse_name': '馬名', 'odds': 'オッズ',
            'win_prob': '1着確率(%)', 'expected_value': '期待値', 'rank': '結果'
        })
        st.dataframe(
            display[['馬番', '馬名', 'オッズ', '1着確率(%)', '期待値', '買い目', '結果']],
            use_container_width=True, hide_index=True
        )

        # 買い目サマリー
        buy_list = result[(result['expected_value'] >= 1.0) & (result['win_prob'] >= 0.15)]
        if len(buy_list) > 0:
            st.subheader("💰 買い目（期待値1.0以上 & 確率15%以上）")
            for _, row in buy_list.iterrows():
                st.write(f"- **{row['number']}番 {row['horse_name']}** "
                         f"（確率{row['win_prob']:.1%} / {row['odds']:.1f}倍 / 期待値{row['expected_value']:.2f}）")
        else:
            st.info("買い目に該当する馬がいません")

        st.caption("⚠️ この予測は過去データに基づくものであり、的中を保証するものではありません。馬券は自己責任でお楽しみください。")
else:
    st.info("👈 左のサイドバーからレースを選んで「予測する」を押してください")
