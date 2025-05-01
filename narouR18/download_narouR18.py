import os
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://novel18.syosetu.com'
TMP_DIR = '/tmp/narouR18_dl'
HISTORY_FILE_NAME = '小説家になろうR18ダウンロード経歴.txt'
HISTORY_PATH = os.path.join(TMP_DIR, HISTORY_FILE_NAME)

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
}
COOKIES = {'over18': 'yes'}

def fetch_url(url):
    return requests.get(url, headers=HEADERS, cookies=COOKIES)

def create_folder(path):
    os.makedirs(path, exist_ok=True)

def sanitize_filename(name):
    return ''.join(c for c in name if c not in r'\/:*?"<>|')

def load_history():
    if not os.path.exists(HISTORY_PATH):
        return {}
    with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
        return dict(line.strip().split('|') for line in f if '|' in line)

def save_history(history):
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        for url, count in history.items():
            f.write(f'{url}|{count}\n')

def get_episode_links(novel_url):
    links = []
    while novel_url:
        res = fetch_url(novel_url)
        soup = BeautifulSoup(res.text, 'html.parser')
        links.extend(soup.select('.p-eplist__sublist .p-eplist__subtitle'))
        next_page = soup.select_one('.c-pager__item--next')
        novel_url = f'{BASE_URL}{next_page["href"]}' if next_page else None
    return links

def download_novel(url, history):
    novel_id = url.rstrip('/').split('/')[-1]
    main_url = f'{BASE_URL}/{novel_id}/'
    res = fetch_url(main_url)
    soup = BeautifulSoup(res.text, 'html.parser')

    title = sanitize_filename(soup.title.get_text(strip=True))
    folder_base = os.path.join(TMP_DIR, title)
    create_folder(folder_base)

    downloaded = int(history.get(url, 0))
    links = get_episode_links(main_url)

    for i, tag in enumerate(links, 1):
        if i <= downloaded:
            continue
        sub_url = f'{BASE_URL}{tag["href"]}'
        sub_res = fetch_url(sub_url)
        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
        text = sub_soup.select_one('.p-novel__body').get_text(strip=True)
        folder = os.path.join(folder_base, f'{((i-1)//999+1):03d}')
        create_folder(folder)
        with open(os.path.join(folder, f'{i:03d}.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'話数 {i} を保存')

    history[url] = str(len(links))

def main():
    create_folder(TMP_DIR)
    history = load_history()

    with open('narouR18/小説家になろうR18.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    for url in urls:
        try:
            download_novel(url, history)
        except Exception as e:
            print(f'エラー: {url} - {e}')

    save_history(history)

if __name__ == '__main__':
    main()
