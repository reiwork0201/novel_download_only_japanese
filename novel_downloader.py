import os
import re
import time
import requests
import urllib.request
import codecs
from bs4 import BeautifulSoup
from urllib.error import HTTPError

# Google Driveとの連携用
from google.colab import drive
import subprocess

# グローバル変数
page_list = []  # 各話のURL
url = ''  # 小説URL
novel_name = ''  # 小説名（自動取得）
history_file = '/content/drive/MyDrive/history.txt'  # history.txtのパス

# Google Driveをマウント
drive.mount('/content/drive')

# HTMLファイルのダウンロード（エラーハンドリング追加）
def loadfromhtml(url: str) -> str:
    try:
        with urllib.request.urlopen(url) as res:
            html_content = res.read().decode()
        return html_content
    except HTTPError as e:
        print(f"エラー: {url} にアクセスできません (HTTP {e.code})")
        return ""  # 空文字を返すことで次の処理へ進む

# 余分なタグを除去
def elimbodytags(base: str) -> str:
    return re.sub('<.*?>', '', base).replace(' ', '')

# カクヨムの小説タイトル取得
def get_novel_title_kakuyomu(body: str) -> str:
    title_match = re.search(r'<title>(.*?) - カクヨム</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"

# ノベルアップ＋の小説タイトル取得
def get_novel_title_novelup(body: str) -> str:
    title_match = re.search(r'<title>(.*?) \| 小説投稿サイトノベルアップ＋</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"

# ノベルアップ＋の目次ページ解析
def parse_novelup_toc():
    global url, page_list
    print("小説情報を取得中...")
    page_number = 1
    while True:
        page_url = f"{url}?p={page_number}"
        body = loadfromhtml(page_url)
        if not body:
            break  # bodyが空なら終了（404などでページが取得できなかった）
        
        # 各話URLの抽出
        ep_pattern = r'<div class="episode_link episode_show_visited">\s*<a href="(https://novelup.plus/story/\d+/\d+)"'
        ep_matches = re.findall(ep_pattern, body)
        
        if not ep_matches:
            break  # 話が無ければ終了
        
        for ep in ep_matches:
            page_list.append(ep)
        
        print(f"ページ {page_number} のURLを取得しました。")
        page_number += 1
    
    print(f"{len(page_list)} 話の目次情報を取得しました。")
    return 0

# 各話の本文解析と保存
def parse_and_save_page(page_url: str, index: int, folder_path: str):
    body = loadfromhtml(page_url)
    
    # 話タイトル取得
    title_match = re.search(r'<div class="episode_title">\s*<h1>(.*?)</h1>', body)
    title = title_match.group(1) if title_match else f"{index}話"
    
    # 本文取得
    content_match = re.search(r'<p id="episode_content">(.*?)</p>', body, re.DOTALL)
    content = elimbodytags(content_match.group(1)) if content_match else "本文取得失敗"
    
    # ファイル保存
    file_name = f"{index:03}.txt"
    file_path = os.path.join(folder_path, file_name)
    
    with codecs.open(file_path, "w", "utf-8") as fout:
        fout.write(f"【タイトル】{title}\r\n\r\n{content}")
    
    print(f"{file_path} に保存しました。")

# 各話のページをダウンロードして保存
def loadeachpage(start_index: int, folder_path: str):
    global page_list
    for i, purl in enumerate(page_list[start_index - 1:], start=start_index):
        parse_and_save_page(purl, i, folder_path)
    
    print(f"{len(page_list) - (start_index - 1)} 話のエピソードを取得しました。")

# history.txtの読み込み
def read_history():
    history = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as file:
            for line in file:
                url, last_chapter = line.strip().split(" | ")
                history[url] = int(last_chapter)
    return history

# history.txtの更新
def update_history(url, last_chapter):
    with open(history_file, 'a', encoding='utf-8') as file:
        file.write(f"{url} | {last_chapter}\n")

# 各サイトに対応する処理
def process_kakuyomu():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_kakuyomu(toppage_content)
    folder_path = f"/content/drive/MyDrive/{novel_name}"
    os.makedirs(folder_path, exist_ok=True)

    # 目次ページの解析
    loadeachpage(read_history().get(url, 1), folder_path)

def process_novelup():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_novelup(toppage_content)
    folder_path = f"/content/drive/MyDrive/{novel_name}"
    os.makedirs(folder_path, exist_ok=True)

    # 目次解析
    if parse_novelup_toc() == 0:
        loadeachpage(read_history().get(url, 1), folder_path)

# メイン処理
def main():
    global url
    history = read_history()

    print("小説ダウンローダー")

    # urls.txtからURLを取得
    with open('urls.txt', 'r') as file:
        urls = file.readlines()
    
    for url_input in urls:
        url = url_input.strip()

        if "kakuyomu.jp" in url:
            process_kakuyomu()

        elif "novelup.plus" in url:
            process_novelup()

        else:
            print(f"{url} はサポートされていないURLです。")
        
        update_history(url, len(page_list))

# スクリプト実行
if __name__ == '__main__':
    main()
