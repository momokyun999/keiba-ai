import requests
import time
import json
from bs4 import BeautifulSoup

horse_id = input("horse_id を入力: ").strip()

url = "https://db.netkeiba.com/horse/ajax_horse_results.html"
params = {"id": horse_id, "input": "UTF-8", "output": "json"}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"https://db.netkeiba.com/horse/{horse_id}/",
}

time.sleep(1)
res = requests.get(url, params=params, headers=headers, timeout=10)
data = res.json()

html_fragment = data["data"]
soup = BeautifulSoup(html_fragment, "html.parser")

table = soup.find("table", class_="db_h_race_results")
if table is None:
    print("テーブルが見つかりません")
else:
    rows = table.find_all("tr")
    print(f"成績テーブル発見（{len(rows)}行）\n")

    # ヘッダー
    header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    print("=== 列見出し ===")
    for i, h in enumerate(header):
        print(f"  [{i}] {h}")

    # 最新（前走）= 2行目
    if len(rows) > 1:
        latest = [c.get_text(strip=True) for c in rows[1].find_all(["th", "td"])]
        print("\n=== 前走（最新レース）===")
        for i, t in enumerate(latest):
            print(f"  [{i}] {t}")