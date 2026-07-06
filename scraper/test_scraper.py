"""
horse_id / jockey_id 抽出テスト
馬名・騎手名のリンク先URLからIDを取り出す
"""
import requests
from bs4 import BeautifulSoup
import time
import re

race_id = "202603020203"

url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

time.sleep(1)
response = requests.get(url, headers=headers, timeout=10)
response.encoding = response.apparent_encoding
soup = BeautifulSoup(response.text, "html.parser")

table = soup.find("table", class_="Shutuba_Table")
rows = table.find_all("tr")

print("=== 各馬のID抽出 ===\n")

for row in rows:
    # 馬名リンクを探す（/horse/ を含むaタグ）
    horse_link = row.find("a", href=re.compile(r"/horse/"))
    jockey_link = row.find("a", href=re.compile(r"/jockey/"))

    if horse_link is None:
        continue  # ヘッダー行などはスキップ

    horse_name = horse_link.get_text(strip=True)
    horse_href = horse_link.get("href", "")
    # URLから数字のIDを抽出
    horse_id_match = re.search(r"/horse/(\d+)", horse_href)
    horse_id = horse_id_match.group(1) if horse_id_match else "不明"

    jockey_name = "不明"
    jockey_id = "不明"
    if jockey_link:
        jockey_name = jockey_link.get_text(strip=True)
        jockey_href = jockey_link.get("href", "")
        jockey_id_match = re.search(r"/jockey/(?:result/recent/)?(\w+)", jockey_href)
        jockey_id = jockey_id_match.group(1) if jockey_id_match else "不明"

    print(f"馬名: {horse_name}")
    print(f"  horse_id: {horse_id}")
    print(f"  騎手: {jockey_name} / jockey_id: {jockey_id}")
    print()