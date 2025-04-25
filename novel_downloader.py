# novel_downloader.py
import os
import requests
import urllib.request
import re
import codecs
from bs4 import BeautifulSoup
from urllib.error import HTTPError
import time
import subprocess

# グローバル変数
page_list = []
url = ''
novel_name = ''
history_map = {}

# HTML取得関数（User-Agent追加）
def loadfromhtml(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            html_content = res.read().decode()
        return html_content
    except HTTPError as e:
        print(f"エラー: {url} にアクセスできません (HTTP {e.code})")
        return ""

# タグ除去
def elimbodytags(base: str) -> str:
    return re.sub('<.*?>', '', base).replace(' ', '')

# タイトル取得関数

def get_novel_title_kakuyomu(body: str) -> str:
    title_match = re.search(r'<title>(.*?) - カクヨム</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"

def get_novel_title_novelup(body: str) -> str:
    title_match = re.search(r'<title>(.*?) \| 小説投稿サイトノベルアップ＋</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"

# history.txtをrcloneでダウンロード

def download_history():
    subprocess.run([
        'rclone', 'copyto', 'remote:history.txt', 'history.txt', '--config', 'rclone.conf'
    ])

# history.txtを更新してGoogle Driveへアップロード
def upload_history():
    with open("history.txt", "w", encoding="utf-8") as f:
        for url, index in history_map.items():
            f.write(f"{url} | {index}\n")
    subprocess.run([
        'rclone', 'copyto', 'history.txt', 'remote:history.txt', '--config', 'rclone.conf'
    ])

# ノベルアップ+の目次解析

def parse_novelup_toc():
    global url, page_list
    page_number = 1
    while True:
        page_url = f"{url}?p={page_number}"
        body = loadfromhtml(page_url)
        if not body:
            break
        ep_pattern = r'<div class="episode_link episode_show_visited">\s*<a href="(https://novelup.plus/story/\d+/\d+)"'
        ep_matches = re.findall(ep_pattern, body)
        if not ep_matches:
            break
        page_list.extend(ep_matches)
        page_number += 1
    return 0

# 各話保存

def parse_and_save_page(page_url: str, index: int):
    body = loadfromhtml(page_url)
    title_match = re.search(r'<div class="episode_title">\s*<h1>(.*?)</h1>', body)
    title = title_match.group(1) if title_match else f"{index}話"
    content_match = re.search(r'<p id="episode_content">(.*?)</p>', body, re.DOTALL)
    content = elimbodytags(content_match.group(1)) if content_match else "本文取得失敗"

    folder_index = (index - 1) // 999 + 1
    subfolder_name = f"{folder_index:03}"
    subfolder_path = os.path.join(novel_name, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)

    file_name = f"{index:03}.txt"
    file_path = os.path.join(subfolder_path, file_name)

    with codecs.open(file_path, "w", "utf-8") as fout:
        fout.write(f"【タイトル】{title}\r\n\r\n{content}")

    print(f"{file_path} に保存しました。")

# 各話処理ループ

def loadeachpage():
    global page_list, novel_name

    # Google Drive フォルダ作成
    subprocess.run([
        'rclone', 'mkdir', f'remote:{novel_name}', '--config', 'rclone.conf'
    ])

    # ローカルにダウンロード済み話数確認
    if os.path.exists(novel_name):
        saved_files = sum([len(files) for r, d, files in os.walk(novel_name) if any(f.endswith('.txt') for f in files)])
        start_index = saved_files + 1
    else:
        start_index = 1

    for i, purl in enumerate(page_list[start_index - 1:], start=start_index):
        parse_and_save_page(purl, i)

        # 1000話ごとにIPバン回避のために一時停止
        if i % 1000 == 0:
            print("--- 1000話処理毎に待機中（IPバン対策） ---")
            time.sleep(60)  # 1分待機（調整可能）

        # 進捗を更新
        history_map[url] = i

    print(f"{len(page_list) - (start_index - 1)} 話のエピソードを取得しました。")

# 各サービス処理

def process_kakuyomu():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_kakuyomu(toppage_content)
    os.makedirs(novel_name, exist_ok=True)
    # TODO: カクヨム用の目次解析を実装する
    loadeachpage()

def process_novelup():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_novelup(toppage_content)
    os.makedirs(novel_name, exist_ok=True)
    if parse_novelup_toc() == 0:
        loadeachpage()

def process_ncode():
    global url, novel_name, page_list
    body = loadfromhtml(url)
    title_match = re.search(r'<title>(.*?) - ', body)
    novel_name = title_match.group(1).strip() if title_match else '無題'
    novel_name = re.sub(r'[\\/:*?"<>|]', '', novel_name)
    os.makedirs(novel_name, exist_ok=True)
    # 目次取得（話URL生成）
    ncode_id = url.strip('/').split('/')[-1]
    api_url = f"https://api.syosetu.com/novelapi/api/?out=json&ncode={ncode_id}"
    json_data = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}).json()
    if len(json_data) < 2:
        return
    total = json_data[0]['general_all_no']
    for i in range(1, total + 1):
        page_list.append(f"https://ncode.syosetu.com/{ncode_id}/{i}/")
    loadeachpage()

def process_novel18():
    global url, novel_name, page_list
    body = loadfromhtml(url)
    title_match = re.search(r'<title>(.*?) - ', body)
    novel_name = title_match.group(1).strip() if title_match else '無題'
    novel_name = re.sub(r'[\\/:*?"<>|]', '', novel_name)
    os.makedirs(novel_name, exist_ok=True)
    # 同様にAPIで話数取得
    ncode_id = url.strip('/').split('/')[-1]
    api_url = f"https://api.syosetu.com/novel18api/api/?out=json&ncode={ncode_id}"
    json_data = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}).json()
    if len(json_data) < 2:
        return
    total = json_data[0]['general_all_no']
    for i in range(1, total + 1):
        page_list.append(f"https://novel18.syosetu.com/{ncode_id}/{i}/")
    loadeachpage()

# メイン処理
def main():
    global url, history_map
    print("小説ダウンローダー起動")

    # history取得
    download_history()
    if os.path.exists("history.txt"):
        with open("history.txt", "r", encoding="utf-8") as f:
            for line in f:
                if '|' in line:
                    u, i = line.strip().split('|')
                    history_map[u.strip()] = int(i.strip())

    if not os.path.exists("urls.txt"):
        print("urls.txt が見つかりません")
        return

    with open("urls.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            url = line
            if url not in history_map:
                history_map[url] = 0

            if "kakuyomu.jp" in url:
                process_kakuyomu()
            elif "novelup.plus" in url:
                process_novelup()
            elif "ncode.syosetu.com" in url:
                process_ncode()
            elif "novel18.syosetu.com" in url:
                process_novel18()
            else:
                print("未対応のURL形式です：", url)

    upload_history()

if __name__ == '__main__':
    main()
