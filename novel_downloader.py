import os
import re
import urllib.request
import codecs
import subprocess
from urllib.error import HTTPError

# グローバル変数
page_list = []
url = ''
novel_name = ''
history_dict = {}
RCLONE_REMOTE = "drive"
RCLONE_CONFIG = "rclone.conf"

# Google Drive のパス
def get_drive_path(filename):
    return f"{RCLONE_REMOTE}:/{filename}"

def download_history():
    if os.path.exists("history.txt"):
        return
    subprocess.run([
        "rclone", "copyto", get_drive_path("history.txt"), "history.txt", "--config", RCLONE_CONFIG
    ], check=False)

def load_history():
    global history_dict
    if not os.path.exists("history.txt"):
        return
    with open("history.txt", "r", encoding="utf-8") as f:
        for line in f:
            if '|' in line:
                u, i = line.strip().split('|')
                history_dict[u.strip()] = int(i.strip())

def update_history():
    global history_dict
    history_dict[url] = len(page_list)
    with open("history.txt", "w", encoding="utf-8") as f:
        for k, v in history_dict.items():
            f.write(f"{k} | {v}\n")
    subprocess.run([
        "rclone", "copyto", "history.txt", get_drive_path("history.txt"), "--config", RCLONE_CONFIG
    ], check=True)

def upload_novel():
    subprocess.run([
        "rclone", "copy", novel_name, get_drive_path(""), "--config", RCLONE_CONFIG, "--update"
    ], check=True)

# ブラウザ風のリクエストを送るためのヘッダー
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

# R18サイト用にcookieを追加
def get_cookies():
    return {'over18': 'yes'}

# URLからHTMLを取得
def loadfromhtml(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={**get_headers(), **get_cookies()})
        with urllib.request.urlopen(req) as res:
            return res.read().decode()
    except HTTPError as e:
        print(f"エラー: {url} にアクセスできません (HTTP {e.code})")
        return ""

def elimbodytags(base: str) -> str:
    return re.sub('<.*?>', '', base).replace(' ', '')

def get_novel_title_kakuyomu(body: str) -> str:
    m = re.search(r'<title>(.*?) - カクヨム</title>', body)
    return re.sub(r'[\\/:*?"<>|]', '', m.group(1).strip()) if m else "無題"

def get_novel_title_novelup(body: str) -> str:
    m = re.search(r'<title>(.*?) \| 小説投稿サイトノベルアップ＋</title>', body)
    return re.sub(r'[\\/:*?"<>|]', '', m.group(1).strip()) if m else "無題"

def get_novel_title_ncode(body: str) -> str:
    m = re.search(r'<p class="novel_title">(.*?)</p>', body)
    return re.sub(r'[\\/:*?"<>|]', '', m.group(1).strip()) if m else "無題"

def parse_kakuyomu_toc():
    global page_list
    html = loadfromhtml(url)
    matches = re.findall(r'<a href="(/works/\d+/episodes/\d+)">', html)
    page_list = ["https://kakuyomu.jp" + m for m in matches]

def parse_novelup_toc():
    global page_list
    page_number = 1
    while True:
        body = loadfromhtml(f"{url}?p={page_number}")
        if not body:
            break
        matches = re.findall(r'<div class="episode_link episode_show_visited">\s*<a href="(https://novelup.plus/story/\d+/\d+)"', body)
        if not matches:
            break
        page_list.extend(matches)
        page_number += 1

def parse_ncode_toc():
    global page_list
    html = loadfromhtml(url)
    page_list = re.findall(r'<a href="(/n\w+/\d+/)">', html)
    page_list = ["https://ncode.syosetu.com" + p for p in page_list]

def parse_novel18_toc():
    global page_list
    html = loadfromhtml(url)
    page_list = re.findall(r'<a href="(/n\w+/\d+/)">', html)
    page_list = ["https://novel18.syosetu.com" + p for p in page_list]

def parse_and_save_page(page_url: str, index: int):
    html = loadfromhtml(page_url)

    if 'kakuyomu.jp' in page_url:
        # タイトル取得
        sect_match = re.search(r'<p class="widget-episodeTitle.*?">.*?</p>', html)
        title = re.sub('<.*?>', '', sect_match.group(0)).strip() if sect_match else f"{index}話"

        # 本文取得
        text_body_pattern = r'<p id="p.*?</p>'
        text_matches = re.findall(text_body_pattern, html)
        content = ""
        for match in text_matches:
            tmp = re.sub('<br\s*/?>', '\r\n', match)
            tmp = re.sub('<.*?>', '', tmp).replace(' ', '')
            content += tmp + "\r\n"
        if not content:
            content = "本文取得失敗"

    elif 'novelup.plus' in page_url:
        title_match = re.search(r'<div class="episode_title">\s*<h1>(.*?)</h1>', html)
        title = title_match.group(1) if title_match else f"{index}話"

        content_match = re.search(r'<p id="episode_content">(.*?)</p>', html, re.DOTALL)
        content = re.sub('<.*?>', '', content_match.group(1)).replace(' ', '') if content_match else "本文取得失敗"

    else:  # syosetu.com（なろう・ノクターン）
        title_match = re.search(r'<p class="novel_subtitle">(.*?)</p>', html)
        title = title_match.group(1).strip() if title_match else f"{index}話"

        content_match = re.search(r'<div id="novel_honbun" class="novel_view">(.*?)</div>', html, re.DOTALL)
        content_html = content_match.group(1) if content_match else ""
        content = re.sub('<br\s*/?>', '\r\n', content_html)
        content = re.sub('<.*?>', '', content).strip()
        if not content:
            content = "本文取得失敗"

    folder_index = (index - 1) // 999 + 1
    subfolder = os.path.join(novel_name, f"{folder_index:03}")
    os.makedirs(subfolder, exist_ok=True)
    file_path = os.path.join(subfolder, f"{index:03}.txt")

    with codecs.open(file_path, "w", "utf-8") as f:
        f.write(f"【タイトル】{title}\r\n\r\n{content}")
    print(f"{file_path} に保存しました。")

def loadeachpage():
    start_index = history_dict.get(url, 0) + 1
    for i, purl in enumerate(page_list[start_index - 1:], start=start_index):
        parse_and_save_page(purl, i)
    print("保存完了。")

def main():
    global url, novel_name
    print("小説ダウンローダー起動")
    download_history()
    load_history()

    with open("urls.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    for u in urls:
        url = u
        if 'kakuyomu.jp' in url:
            html = loadfromhtml(url)
            novel_name = get_novel_title_kakuyomu(html)
            parse_kakuyomu_toc()
        elif 'novelup.plus' in url:
            html = loadfromhtml(url)
            novel_name = get_novel_title_novelup(html)
            parse_novelup_toc()
        elif 'ncode.syosetu.com' in url:
            html = loadfromhtml(url)
            novel_name = get_novel_title_ncode(html)
            parse_ncode_toc()
        elif 'novel18.syosetu.com' in url:
            html = loadfromhtml(url)
            novel_name = get_novel_title_ncode(html)
            parse_novel18_toc()
        else:
            print(f"サポート外: {url}")
            continue

        os.makedirs(novel_name, exist_ok=True)
        loadeachpage()
        upload_novel()

    update_history()

if __name__ == '__main__':
    main()
