import os
import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://novel18.syosetu.com'

def fetch_url(url):
    """
    指定されたURLからウェブページの内容を取得します。
    User-AgentヘッダーとCookieを設定して、アクセスをエミュレートします。
    """
    ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
    headers = {'User-Agent': ua}
    cookies = {'over18': 'yes'}
    return requests.get(url, headers=headers, cookies=cookies)

def create_folder(path):
    """
    指定されたパスにフォルダを作成します。
    フォルダが既に存在する場合は、エラーを無視します。
    """
    os.makedirs(path, exist_ok=True)

def sanitize_filename(filename):
    """
    ファイル名からWindowsで許可されていない文字を削除します。
    """
    invalid_chars = r'\/:*?"<>|'
    return ''.join(c for c in filename if c not in invalid_chars)

def read_history():
    """
    Google Drive からのダウンロード履歴を読み込み、次にダウンロードすべき話数を取得します。
    履歴ファイルは URL | 最終話数 の形式です。
    """
    history_file = '/tmp/narouR18_dl/小説家になろうR18ダウンロード経歴.txt'
    history = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='UTF-8') as f:
            lines = f.readlines()
        for line in lines:
            # URL | 最終話数 の形式
            url, last_chapter = line.split(' | ')
            history[url.strip()] = int(last_chapter.strip())
    return history

def update_history(novel_url, last_chapter):
    """
    履歴ファイルを更新します。指定された小説の最後のダウンロード話数を記録します。
    """
    history_file = '/tmp/narouR18_dl/小説家になろうR18ダウンロード経歴.txt'
    with open(history_file, 'a', encoding='UTF-8') as f:
        f.write(f'{novel_url} | {last_chapter}\n')

def download_novel(novel_id, history):
    """
    小説のURLを指定して、その小説をダウンロードします。
    """
    DOWNLOAD_URL = f'{BASE_URL}/{novel_id}/'
    url = DOWNLOAD_URL
    sublist = []
    title_text = ""
    last_chapter = history.get(DOWNLOAD_URL, 0)  # 履歴ファイルに基づき開始話数を決定

    while True:
        res = fetch_url(url)
        soup = BeautifulSoup(res.text, 'html.parser')

        if not title_text:
            title_text = soup.find('title').get_text()
        
        sublist.extend(soup.select('.p-eplist__sublist .p-eplist__subtitle'))

        next_page = soup.select_one('.c-pager__item--next')
        if next_page and next_page.get('href'):
            url = f'{BASE_URL}{next_page["href"]}'
        else:
            break

    title_text = sanitize_filename(title_text)
    create_folder(f'./{title_text}')
    
    file_count = last_chapter + 1
    sub_len = len(sublist)

    for i, sub in enumerate(sublist[last_chapter:], 1):
        sub_title = sub.text.strip()
        link = sub.get('href')

        folder_num = ((file_count - 1) // 999) + 1
        folder_name = f'{folder_num:03d}'
        folder_path = f'./{title_text}/{folder_name}'
        create_folder(folder_path)

        file_name = f'{file_count:03d}.txt'
        file_path = f'{folder_path}/{file_name}'

        if os.path.exists(file_path):
            print(f'{file_name} は既に存在します。スキップします... ({i}/{sub_len})')
            file_count += 1
            continue

        res = fetch_url(f'{BASE_URL}{link}')
        soup = BeautifulSoup(res.text, 'html.parser')
        sub_body_text = soup.select_one('.p-novel__body').text

        with open(file_path, 'w', encoding='UTF-8') as f:
            f.write(sub_body_text)

        print(f'{file_name} をダウンロードしました ({i}/{sub_len})')
        file_count += 1

    update_history(DOWNLOAD_URL, file_count - 1)

def main():
    """
    メイン関数：
    1. 小説IDをリポジトリの履歴ファイルから取得
    2. 各小説をダウンロード
    """
    history = read_history()

    # 小説家になろうR18.txt から URL を取得
    with open('./narouR18/小説家になろうR18.txt', 'r', encoding='UTF-8') as f:
        urls = f.readlines()

    for url in urls:
        url = url.strip()
        novel_id = url.split('/')[-2]  # ID を URL から抽出
        download_novel(novel_id, history)

if __name__ == '__main__':
    main()
