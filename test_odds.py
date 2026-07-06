"""
オッズ取得関数
predict_live.py の get_shutuba() の後に追加し、
main()で呼び出してdfにマージする。
"""
import requests
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def get_odds(race_id):
    """
    netkeibaのオッズAPIから単勝オッズと人気を取得。
    返り値: {馬番(int): {'odds': float, 'popularity': int}}
    """
    api_url = (f"https://race.netkeiba.com/api/api_get_jra_odds.html"
               f"?race_id={race_id}&type=1")
    time.sleep(1)
    res = requests.get(api_url, headers=HEADERS, timeout=10)
    data = res.json()

    odds_dict = {}
    try:
        # data > odds > "1"（単勝） > 馬番 > [オッズ, _, 人気]
        tansho = data["data"]["odds"]["1"]
        for umaban_str, values in tansho.items():
            umaban = int(umaban_str)
            odds_val = float(values[0]) if values[0] not in ("", "0.0") else None
            pop_val = int(values[2]) if values[2] else None
            odds_dict[umaban] = {"odds": odds_val, "popularity": pop_val}
    except (KeyError, ValueError, IndexError) as e:
        print(f"  オッズ解析エラー: {e}")

    return odds_dict


def merge_odds(df, race_id):
    """出馬表DataFrameにオッズと人気をマージ"""
    odds_dict = get_odds(race_id)

    if not odds_dict:
        print("  オッズ取得失敗 → 仮値で続行")
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

    # オッズが取れた頭数を報告
    n_odds = df["odds"].notna().sum()
    print(f"  → オッズ取得: {n_odds}頭 / {len(df)}頭")

    # 万一欠損があれば中央値で補完
    if df["odds"].isna().any():
        median_odds = df["odds"].median()
        df["odds"] = df["odds"].fillna(median_odds)
        df["popularity"] = df["popularity"].fillna(df["popularity"].max())

    return df


# ===== 動作テスト =====
if __name__ == "__main__":
    race_id = input("race_id: ").strip()
    odds = get_odds(race_id)
    print(f"\n取得したオッズ（{len(odds)}頭）:")
    for umaban in sorted(odds.keys()):
        o = odds[umaban]
        print(f"  馬番{umaban:>2}: {o['odds']}倍 ({o['popularity']}番人気)")