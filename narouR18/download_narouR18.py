import os
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://novel18.syosetu.com'
TMP_DIR = '/tmp/narouR18_dl'
HISTORY_FILE = f'{TMP_DIR}/小説家になろうR18ダウンロード経歴.txt'
URL_LIST_PATH = 'narouR18/小説家になろうR18.txt'

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
}
COOKIES = {
    'over18': 'yes',
}

def fetch_html(url):
    res = requests.get(url, headers=HEADERS, cookies=COOKIES)
    res.raise_for_status()
    return BeautifulSoup(res.text, 'html.parser')

def sanitize_filename(name):
    return ''.join(c for c in name if c not in r'\/:*?"<>|')

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return dict(line.strip().split('|') for line in f if '|' in line)

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        for url, last_num in history.items():
            f.write(f'{url}|{last_num}\n')

def create_folder(path):
    os.makedirs(path, exist_ok=True)

def download_novel(novel_url, history):
    soup = fetch_html(novel_url)
    title = sanitize_filename(soup.title.text.strip())
    novel_folder = os.path.join(TMP_DIR, title)
    create_folder(novel_folder)

    episodes = soup.select('.p-eplist__sublist .p-eplist__subtitle')
    last_saved = int(history.get(novel_url, '0'))
    new_last = last_saved

    for i, ep in enumerate(episodes, 1):
        if i <= last_saved:
            continue

        ep_url = BASE_URL + ep['href']
        ep_title = ep.text.strip()
        ep_page = fetch_html(ep_url)
        body = ep_page.select_one('.p-novel__body').text.strip()

        folder_index = f'{((i - 1) // 999 + 1):03d}'
        folder_path = os.path.join(novel_folder, folder_index)
        create_folder(folder_path)

        file_path = os.path.join(folder_path, f'{i:03d}.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(body)
        print(f'Downloaded: {file_path}')
        new_last = i

    history[novel_url] = str(new_last)

def main():
    create_folder(TMP_DIR)
    with open(URL_LIST_PATH, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('https')]

    history = load_history()
    for url in urls:
        download_novel(url, history)
    save_history(history)

if __name__ == '__main__':
    main()
