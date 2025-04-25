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
page_list = []  # 各話のURL
url = ''  # 小説URL
novel_name = ''  # 小説名（自動取得）


# HTMLファイルのダウンロード（User-Agent追加）
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
def parse_and_save_page(page_url: str, index: int):
    body = loadfromhtml(page_url)
    
    # 話タイトル取得
    title_match = re.search(r'<div class="episode_title">\s*<h1>(.*?)</h1>', body)
    title = title_match.group(1) if title_match else f"{index}話"
    
    # 本文取得
    content_match = re.search(r'<p id="episode_content">(.*?)</p>', body, re.DOTALL)
    content = elimbodytags(content_match.group(1)) if content_match else "本文取得失敗"
    
    # ファイル保存
    folder_index = (index - 1) // 999 + 1  # サブフォルダ番号（999話ごと）
    subfolder_name = f"{folder_index:03}"
    subfolder_path = os.path.join(novel_name, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)
    
    file_name = f"{index:03}.txt"
    file_path = os.path.join(subfolder_path, file_name)
    
    with codecs.open(file_path, "w", "utf-8") as fout:
        fout.write(f"【タイトル】{title}\r\n\r\n{content}")
    
    print(f"{file_path} に保存しました。")


# 各話のページをダウンロードして保存
def loadeachpage():
    global page_list
    
    # 既存のフォルダチェックとダウンロード済みファイル確認
    if os.path.exists(novel_name):
        # 保存されている話数をカウント
        saved_files = 0
        for subfolder in os.listdir(novel_name):
            subfolder_path = os.path.join(novel_name, subfolder)
            if os.path.isdir(subfolder_path):
                for file in os.listdir(subfolder_path):
                    if file.endswith('.txt'):
                        saved_files += 1
        print(f"すでに {saved_files} 話がダウンロードされています。")
        start_index = saved_files + 1  # 既にダウンロードされたファイル数から再開
    else:
        start_index = 1  # フォルダがない場合は最初から

    # ダウンロードされていない話からダウンロードを開始
    for i, purl in enumerate(page_list[start_index - 1:], start=start_index):
        parse_and_save_page(purl, i)
    
    print(f"{len(page_list) - (start_index - 1)} 話のエピソードを取得しました。")


# それぞれのサイトに対応する処理
def process_kakuyomu():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_kakuyomu(toppage_content)
    os.makedirs(novel_name, exist_ok=True)

    # 目次ページの解析
    # ... カクヨム用の目次解析コードを追加

    loadeachpage()


def process_novelup():
    global url, novel_name, page_list
    toppage_content = loadfromhtml(url)
    novel_name = get_novel_title_novelup(toppage_content)
    os.makedirs(novel_name, exist_ok=True)

    # 目次解析
    if parse_novelup_toc() == 0:
        loadeachpage()


def process_ncode():
    # ncode.syosetu.com 用の処理
    pass  # 詳細は上記のコードで既に実装


def process_novel18():
    # novel18.syosetu.com 用の処理
    pass  # 詳細は上記のコードで既に実装


# メイン処理
def main():
    global url

    print("小説ダウンローダー")

    while True:
        url_input = input("小説のトップページURLを入力してください (カクヨム、ノベルアップ＋、ncode.syosetu.com、novel18.syosetu.com): ").strip()
        if re.match(r'https?://', url_input):  # URLの形式確認
            url = url_input
            break
        else:
            print("正しいURLを入力してください。")

    if "kakuyomu.jp" in url:
        process_kakuyomu()

    elif "novelup.plus" in url:
        process_novelup()

    elif "ncode.syosetu.com" in url:
        process_ncode()

    elif "novel18.syosetu.com" in url:
        process_novel18()

    else:
        print("サポートされていないURLです。")

# スクリプト実行
if __name__ == '__main__':
    main()
