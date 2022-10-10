import io
import sys
import time
import unicodedata
from argparse import ArgumentParser
from urllib import robotparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

#sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
#sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_robots_txt(base_url):
    robots_txt_url = f'{base_url}/robots.txt'
    targets_url = [f'{base_url}/', 
                   f'{base_url}/categories/',
                   f'{base_url}/topics/',
                   ]
    user_agent = '*'

    # robots.txtの取得
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_txt_url)
    rp.read()
    time.sleep(1)

    not_list = []

    # 各URLがスクレイピング可能かチェックする
    for url in targets_url:
        res = rp.can_fetch(user_agent, f'{url}*')
        if res is False:
            print(f'can not scrape: {url}')
            not_list.append(url)

    return len(not_list) == 0


def get_target_categories(target):
    items = {'m': '主要',
             'd': '国内',
             'b': '経済',
             'e': 'エンタメ',
             'w': '国際',
             }
    item_list = []

    for k in target:
        item_list.append(items[k])

    return item_list


def head_line_long(target):
    base_url = 'https://news.yahoo.co.jp/topics/'

    categories = {
        '主要': 'top-picks',
        '国内': 'domestic',
        '経済': 'business',
        'エンタメ': 'entertainment',
        '国際': 'world',
        }
    
    # カテゴリーごとにループ処理する
    for cat in get_target_categories(target):
        url = urljoin(base_url, categories[cat])

        r = requests.get(url)
        time.sleep(1)

        soup = BeautifulSoup(r.content, 'lxml') # html.parser

        div_tag = soup.find('div', class_='newsFeed')
        if div_tag is None:
            print('div_tag.newsFeed is None.')
            sys.exit()

        ul_tag = div_tag.find('ul', class_='newsFeed_list')
        if ul_tag is None:
            print('ul_tag is None.')
            sys.exit()

        print(f'＝＝＝{cat}＝＝＝')

        for item in ul_tag.find_all('li', class_='newsFeed_item'):
            a = item.find('a')
            if a is None: continue
            topic_url = a['href']

            div_tag = a.find('div', class_='newsFeed_item_title')
            if div_tag is None:
                print('div_tag.newsFeed_item_title is None.')
                sys.exit()

            topic_headline = div_tag.text.strip()

            if topic_headline.endswith('オリジナル'):
                topic_headline = topic_headline[:-5]

            text = text_align(topic_headline, 34)
            print(f'{text}[{topic_url}]')

        print()


def head_line_short(target):
    base_url = 'https://news.yahoo.co.jp/'

    # 主要[m], 国内[d], 経済[b], エンタメ[e], 国際[w]
    categories = {
        '主要': '',
        '国内': 'categories/domestic',
        '経済': 'categories/business',
        'エンタメ': 'categories/entertainment',
        '国際': 'categories/world',
        }

    # カテゴリーごとにループ処理する
    #for cat in categories:
    for cat in get_target_categories(target):
        url = urljoin(base_url, categories[cat])

        r = requests.get(url)
        time.sleep(1)

        soup = BeautifulSoup(r.content, 'lxml') # html.parser

        div_tag = soup.select_one('#uamods-topics > div > div > div')
        if div_tag is None:
            print('div_tag is None.')
            break
        ul_tag = div_tag.find('ul')
        if ul_tag is None:
            print('ul_tag is None.')
            break

        print(f'＝＝＝{cat}＝＝＝')

        for item in ul_tag.find_all('li'):
            a = item.find('a')
            topic_url = a['href']
            topic_headline = a.text.strip()

            if topic_headline.endswith('オリジナル'):
                topic_headline = topic_headline[:-5]
            
            #print(f'{topic_headline:<18}[{topic_url}]')
            text = text_align(topic_headline, 34)
            print(f'{text}[{topic_url}]')

        print()

def get_han_count(text):
    '''
    全角文字は「２」、半角文字は「１」として文字列の長さを計算する
    '''
    count = 0

    for char in text:
        if unicodedata.east_asian_width(char) in 'FWA':
            count += 2
        else:
            count += 1

    return count

def text_align(text, width, *, align=-1, fill_char=' '):
    '''
    全角／半角が混在するテキストを
    指定の長さ（半角換算）になるように空白などで埋める
    
    width: 半角換算で文字数を指定
    align: -1 -> left, 1 -> right
    fill_char: 埋める文字を指定

    return: 空白を埋めたテキスト（'abcde     '）
    '''

    fill_count = width - get_han_count(text)
    if fill_count <= 0: return text

    if align < 0:
        return text + fill_char*fill_count
    else:
        return fill_char*fill_count + text

if __name__ == '__main__':
    # ターゲットサイトの'robots.txt'をチェックする
    if not check_robots_txt('https://news.yahoo.co.jp'):
        print('Webスクレイピングが禁止されています。')
        sys.exit()

    # コマンドライン引数の処理（'-f'を付けるとフル版、付けないと短縮版）
    parser = ArgumentParser()
    parser.add_argument('-f', '--full', action='store_true')
    args = parser.parse_args()

    print('取得するニュースのジャンルを指定してください。（例：me, b, ...）')
    target = input('主要[m], 国内[d], 経済[b], エンタメ[e], 国際[w]: ')
    print()

    if args.full:
        head_line_long(target)
    else:
        head_line_short(target)


