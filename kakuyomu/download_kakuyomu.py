import os
import re
import time
import subprocess
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://kakuyomu.jp'
HISTORY_FILE = 'カクヨムダウンロード経歴.txt'
LOCAL_HISTORY_PATH = f'/tmp/{HISTORY_FILE}'
REMOTE_HISTORY_PATH = f'drive:{HISTORY_FILE}'

def fetch_url(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res

def parsetoppage(body: str, work_url: str) -> list[str]:
    episode_urls = []
    ep_pattern = r'"__typename":"Episode","id":".*?","title":".*?",'
    ep_matches = re.findall(ep_pattern, body)

    if not ep_matches:
        print("指定されたページからエピソード情報を取得できませんでした。")
        return []

    for ep in ep_matches:
        purl_id_match = re.search(r'"id":"(.*?)"', ep)
        if purl_id_match:
            purl_id = purl_id_match.group(1)
            purl_full_url = f"{work_url}/episodes/{purl_id}"
            episode_urls.append(purl_full_url)

    return episode_urls

def extract_episode_content(body: str) -> tuple[str, str]:
    title_match = re.search(r'<p class="widget-episodeTitle.*?">.*?</p>', body)
    title_cleaned = re.sub('<.*?>', '', title_match.group(0)).strip() if title_match else "無題"

    text_body_pattern = r'<p id="p.*?</p>'
    text_matches = re.findall(text_body_pattern, body)

    text_content = ""
    for match in text_matches:
        line = re.sub('<br ?/?>', '\r\n', match)
        line = re.sub('<.*?>', '', line).replace(' ', '')
        text_content += line + "\r\n"

    return title_cleaned, text_content

def load_history():
    if not os.path.exists(LOCAL_HISTORY_PATH):
        subprocess.run(['rclone', 'copyto', REMOTE_HISTORY_PATH, LOCAL_HISTORY_PATH], check=False)

    history = {}
    if os.path.exists(LOCAL_HISTORY_PATH):
        with open(LOCAL_HISTORY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'(https?://[^\s|]+)\s*\|\s*(\d+)', line.strip())
                if match:
                    url, last = match.groups()
                    history[url.rstrip('/')] = int(last)
    return history

def save_history(history):
    with open(LOCAL_HISTORY_PATH, 'w', encoding='utf-8') as f:
        for url, last in history.items():
            f.write(f'{url}  |  {last}\n')
    subprocess.run(['rclone', 'copyto', LOCAL_HISTORY_PATH, REMOTE_HISTORY_PATH], check=True)

# URL一覧の読み込み
script_dir = os.path.dirname(__file__)
url_file_path = os.path.join(script_dir, 'カクヨム.txt')
with open(url_file_path, 'r', encoding='utf-8') as f:
    urls = [line.strip().rstrip('/') for line in f if line.strip().startswith('http')]

history = load_history()

for novel_url in urls:
    try:
        print(f'\n--- 処理開始: {novel_url} ---')
        res = fetch_url(novel_url)
        body = res.text
        soup = BeautifulSoup(body, 'html.parser')
        title_text = soup.title.get_text()
        for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            title_text = title_text.replace(char, '')
        title_text = title_text.strip()

        episode_urls = parsetoppage(body, novel_url)
        download_from = history.get(novel_url, 0)
        os.makedirs(f'/tmp/kakuyomu_dl/{title_text}', exist_ok=True)

        new_max = download_from
        for i, episode_url in enumerate(episode_urls):
            if i + 1 <= download_from:
                continue

            # 300話ごとに1分待機
            if i != 0 and i % 300 == 0:
                print("300話処理したため、60秒待機します...")
                time.sleep(60)

            res = fetch_url(episode_url)
            title, content = extract_episode_content(res.text)

            file_name = f'{i+1:03d}.txt'
            folder_num = (i // 999) + 1
            folder_name = f'{folder_num:03d}'
            folder_path = f'/tmp/kakuyomu_dl/{title_text}/{folder_name}'
            os.makedirs(folder_path, exist_ok=True)
            file_path = f'{folder_path}/{file_name}'

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f'{title}\n\n{content}')

            print(f'{file_name} downloaded in folder {folder_name} ({i+1}/{len(episode_urls)})')
            new_max = i + 1

        history[novel_url] = new_max

    except Exception as e:
        print(f'エラー発生: {novel_url} → {e}')
        continue

save_history(history)

# Google Driveへアップロード
subprocess.run([
    'rclone', 'copy', '/tmp/kakuyomu_dl', 'drive:/kakuyomu_dl',
    '--create-dirs', '--transfers=4', '--checkers=8', '--fast-list'
], check=True)
