import os
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://ncode.syosetu.com'

def fetch_url(url):
    ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
    headers = {'User-Agent': ua}
    return requests.get(url, headers=headers)

# ファイルからURL一覧を読み込む
with open('小説家になろう.txt', 'r', encoding='utf-8') as f:
    urls = [line.strip().rstrip('/') for line in f if line.strip().startswith('http')]

for novel_url in urls:
    try:
        print(f'\n--- 処理開始: {novel_url} ---')
        url = novel_url
        sublist = []

        # ページ分割対応（複数ページの目次取得）
        while True:
            res = fetch_url(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            title_text = soup.find('title').get_text()
            sublist += soup.select('.p-eplist__sublist .p-eplist__subtitle')
            next = soup.select_one('.c-pager__item--next')
            if next and next.get('href'):
                url = f'{BASE_URL}{next.get("href")}'
            else:
                break

        # フォルダ名から禁止文字を除去
        for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            title_text = title_text.replace(char, '')
        title_text = title_text.strip()

        os.makedirs(f'./{title_text}', exist_ok=True)

        sub_len = len(sublist)
        for i, sub in enumerate(sublist):
            sub_title = sub.text.strip()
            link = sub.get('href')
            file_name = f'{i+1:03d}.txt'
            folder_num = (i // 999) + 1
            folder_name = f'{folder_num:03d}'
            folder_path = f'./{title_text}/{folder_name}'
            os.makedirs(folder_path, exist_ok=True)

            file_path = f'{folder_path}/{file_name}'
            if os.path.exists(file_path):
                print(f'{file_name} already exists. Skipping... ({i+1}/{sub_len})')
                continue

            res = fetch_url(f'{BASE_URL}{link}')
            soup = BeautifulSoup(res.text, 'html.parser')
            sub_body = soup.select_one('.p-novel__body')
            sub_body_text = sub_body.get_text() if sub_body else '[本文が取得できませんでした]'

            with open(file_path, 'w', encoding='UTF-8') as f:
                f.write(f'{sub_title}\n\n{sub_body_text}')
            print(f'{file_name} downloaded in folder {folder_name} ({i+1}/{sub_len})')

    except Exception as e:
        print(f'エラー発生: {novel_url} → {e}')
        continue
