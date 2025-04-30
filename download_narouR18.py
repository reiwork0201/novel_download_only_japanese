import os
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://novel18.syosetu.com'
TMP_DIR = '/tmp/narouR18_dl'  # 保存先を変更
HISTORY_FILE = '小説家になろうR18ダウンロード経歴.txt'
HISTORY_PATH = os.path.join(TMP_DIR, HISTORY_FILE)

def fetch_url(url):
    ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
    headers = {'User-Agent': ua}
    cookies = {'over18': 'yes'}
    return requests.get(url, headers=headers, cookies=cookies)

def create_folder(path):
    os.makedirs(path, exist_ok=True)

def sanitize_filename(filename):
    invalid_chars = r'\\/:*?\"<>|'
    return ''.join(c for c in filename if c not in invalid_chars)

def load_history():
    history = {}
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    url, count = line.strip().split('|')
                    history[url.strip()] = int(count)
    return history

def save_history(history):
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        for url, count in history.items():
            f.write(f'{url} | {count}\n')

def main():
    novel_id = input("小説IDを入力してください (例: n1234abcd): ")
    novel_url = f'{BASE_URL}/{novel_id}/'

    # 履歴ファイルをDriveから取得（GitHub Actionsではrcloneで取得前提）
    os.system(f"rclone copy drive:{HISTORY_FILE} {TMP_DIR} --drive-shared-with-me --update")

    history = load_history()
    latest_downloaded = history.get(novel_url, 0)

    url = novel_url
    sublist = []

    while True:
        res = fetch_url(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        title_text = soup.find('title').get_text()
        sublist.extend(soup.select('.p-eplist__sublist .p-eplist__subtitle'))

        next_page = soup.select_one('.c-pager__item--next')
        if next_page and next_page.get('href'):
            url = f'{BASE_URL}{next_page["href"]}'
        else:
            break

    title_text = sanitize_filename(title_text)
    base_path = os.path.join(TMP_DIR, title_text)
    create_folder(base_path)

    sub_len = len(sublist)
    file_count = 1
    new_latest = latest_downloaded

    for i, sub in enumerate(sublist, 1):
        if i <= latest_downloaded:
            print(f'{i:03d}.txt は履歴によりスキップされました ({i}/{sub_len})')
            file_count += 1
            continue

        sub_title = sub.text.strip()
        link = sub.get('href')

        folder_num = ((file_count - 1) // 999) + 1
        folder_name = f'{folder_num:03d}'
        folder_path = os.path.join(base_path, folder_name)
        create_folder(folder_path)

        file_name = f'{file_count:03d}.txt'
        file_path = os.path.join(folder_path, file_name)

        res = fetch_url(f'{BASE_URL}{link}')
        soup = BeautifulSoup(res.text, 'html.parser')
        sub_body_text = soup.select_one('.p-novel__body').text

        with open(file_path, 'w', encoding='UTF-8') as f:
            f.write(sub_body_text)

        print(f'{file_name} をダウンロードしました ({i}/{sub_len})')
        file_count += 1
        new_latest = i

    if new_latest > latest_downloaded:
        history[novel_url] = new_latest
        save_history(history)
        os.system(f"rclone copy {HISTORY_PATH} drive:{HISTORY_FILE} --drive-shared-with-me --update")
        print(f'履歴ファイルを更新しアップロードしました。最新話数: {new_latest}')
    else:
        print('新規ダウンロードはありませんでした。')

if __name__ == '__main__':
    create_folder(TMP_DIR)
    main()
