import sys
import codecs
import urllib.request
import re
import time
import os
import subprocess

# グローバル変数
page_list = []  # 各話のURL
url = ''  # 小説URL
startn = 0  # DL開始番号
novel_name = ''  # 小説名（自動取得）
history_file = 'カクヨムダウンロード経歴.txt'  # 履歴ファイルのパス
history = {}  # URL | 最終話数の履歴情報

# HTMLファイルのダウンロード
def loadfromhtml(url: str) -> str:
    with urllib.request.urlopen(url) as res:
        html_content = res.read().decode()
    return html_content

# 余分なタグを除去
def elimbodytags(base: str) -> str:
    return re.sub('<.*?>', '', base).replace(' ', '')

# 改行タグを変換
def changebrks(base: str) -> str:
    return re.sub('<br />', '\r\n', base)

# タグ変換とフィルター実行
def tagfilter(line: str) -> str:
    tmp = changebrks(line)
    tmp = elimbodytags(tmp)
    return tmp

# 小説タイトルの取得
def get_novel_title(body: str) -> str:
    title_match = re.search(r'<title>(.*?) - カクヨム</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        # フォルダ名として使えない文字を削除
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"

# 目次ページの解析と各話のURL取得
def parsetoppage(body: str) -> int:
    global url, page_list

    print("小説情報を取得中...")

    # 各エピソードの URL を取得
    ep_pattern = r'"__typename":"Episode","id":".*?","title":".*?",'
    ep_matches = re.findall(ep_pattern, body)

    if not ep_matches:
        print("指定されたページからエピソード情報を取得できませんでした。")
        return -1

    for ep in ep_matches:
        purl_id_match = re.search(r'"id":"(.*?)"', ep)
        if purl_id_match:
            purl_id = purl_id_match.group(1)
            purl_full_url = f"{url}/episodes/{purl_id}"
            page_list.append(purl_full_url)

    print(f"{len(page_list)} 話の目次情報を取得しました。")
    return 0

# 各話の本文解析と保存処理
def parsepage(body: str, index: int):
    global novel_name

    # 話タイトル取得
    sect_match = re.search(r'<p class="widget-episodeTitle.*?">.*?</p>', body)

    if sect_match:
        sect_title = sect_match.group(0)
        sect_title_cleaned = re.sub('<.*?>', '', sect_title).strip()

        # 本文取得
        text_body_pattern = r'<p id="p.*?</p>'
        text_matches = re.findall(text_body_pattern, body)

        text_content = ""
        for match in text_matches:
            cleaned_text = tagfilter(match)
            text_content += cleaned_text + "\r\n"

        if text_content:
            folder_index = (index - 1) // 999 + 1  # サブフォルダ番号（999話ごと）
            subfolder_name = f"{folder_index:03}"
            subfolder_path = os.path.join(novel_name, subfolder_name)

            os.makedirs(subfolder_path, exist_ok=True)  # サブフォルダ作成

            # ファイル名生成（ゼロ埋め）
            file_name_prefix = f"{index:03}"
            file_name = f"{file_name_prefix}.txt"
            file_path = os.path.join(subfolder_path, file_name)

            if os.path.exists(file_path):  # 既に存在する場合はスキップ
                print(f"{file_path} は既に存在します。スキップします。")
                return

            with codecs.open(file_path, "w", "utf-8") as fout:
                fout.write(f"【タイトル】{sect_title_cleaned}\r\n\r\n{text_content}")

            print(f"{file_path} に保存しました。")
        else:
            print(f"{index} 話の本文が見つかりませんでした。")

# 各話のページをダウンロードして保存
def loadeachpage() -> int:
    n_pages_to_download = len(page_list)

    for i, purl in enumerate(page_list[startn:], start=startn + 1):
        page_content = loadfromhtml(purl)
        if page_content:
            parsepage(page_content, i)
            time.sleep(0.01)  # サーバー負荷軽減

    print(f"{n_pages_to_download - startn} 話のエピソードを取得しました。")

# 小説ファイルを Google Drive にアップロード
def upload_to_drive():
    # Google Drive にアップロードする処理を subprocess で実行
    os.system(f"rclone move {novel_name} drive:/kakuyomu_dl/ --create-dirs --transfers=1 --progress")
    print(f"{novel_name} を Google Drive にアップロードしました。")

# 履歴ファイルを読み込む
def load_history():
    global history
    try:
        # Google Drive から履歴ファイルをダウンロード
        subprocess.run(["rclone", "copy", "drive:/カクヨムダウンロード経歴.txt", history_file, "--progress"])
        # 履歴ファイルを読み込む
        with open(history_file, 'r', encoding='utf-8') as f:
            for line in f:
                url, last_chapter = line.strip().split(' | ')
                history[url] = int(last_chapter)
    except Exception as e:
        print(f"履歴の読み込みに失敗しました: {e}")

# 履歴ファイルをアップロードする
def upload_history():
    try:
        subprocess.run(["rclone", "copy", history_file, "drive:/カクヨムダウンロード経歴.txt", "--progress"])
        print("履歴ファイルを Google Drive にアップロードしました。")
    except Exception as e:
        print(f"履歴のアップロードに失敗しました: {e}")

# 履歴に基づいてダウンロード開始位置を決定
def set_start_index():
    global startn
    # 履歴に基づいて最終話数を取得
    if url in history:
        startn = history[url] + 1  # 次の話からダウンロード開始
        print(f"履歴に基づき、{startn} 話目からダウンロードを開始します。")
    else:
        startn = 0  # 履歴がなければ最初から
        print("履歴がないため、最初からダウンロードを開始します。")

# メイン処理
def main():
    global url, startn, novel_name

    print("kakudlpy ver1.1 2025/03/07 (c) INOUE, masahiro")

    # カクヨム.txt から URL を取得
    try:
        with open('kakuyomu/カクヨム.txt', 'r', encoding='utf-8') as f:
            url_input = f.readline().strip()  # URL を読み取る
            if re.match(r'https://kakuyomu.jp/works/\d{19,20}', url_input):
                url = url_input
                print(f"取得したURL: {url}")
            else:
                print("正しいカクヨム作品トップページURLがカクヨム.txtにありません。")
                return
    except FileNotFoundError:
        print("カクヨム.txt ファイルが見つかりません。")
        return

    # 履歴ファイルを読み込む
    load_history()

    # 目次ページのHTMLを取得
    toppage_content = loadfromhtml(url)

    if not toppage_content:
        print("ページの取得に失敗しました。")
        return

    # 小説タイトルを取得
    novel_name = get_novel_title(toppage_content)
    print(f"取得した小説名: {novel_name}")

    # フォルダ名として使用できない文字を削除
    novel_name = re.sub(r'[\\/:*?"<>|]', '', novel_name)

    # フォルダ作成
    os.makedirs(novel_name, exist_ok=True)

    # 履歴に基づいてダウンロード開始位置を決定
    set_start_index()

    # 目次解析
    if parsetoppage(toppage_content) == 0:
        loadeachpage()

    # 小説ファイルのアップロード
    upload_to_drive()

    # 新しい履歴を保存してアップロード
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write(f"{url} | {len(page_list)}\n")
    upload_history()

# スクリプト実行
if __name__ == '__main__':
    main()
