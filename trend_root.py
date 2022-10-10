import datetime
import json
import os
import re
import time

import pandas as pd
import tweepy

# リツイートからアカウント名を抽出するための正規表現
RT_PATTERN = re.compile(r'RT (@.+): ')

# UTCとJSTの時差
TIME_DELTA = datetime.timedelta(hours = 9)

def init_twitter_api():
    # 環境変数から認証情報を取得する
    BEARER_TOKEN = os.environ['TWITTER_BEARER_TOKEN']
    API_KEY = os.environ['TWITTER_API_KEY']
    API_KEY_SECRET = os.environ['TWITTER_API_SECRET_KEY']
    ACCESS_TOKEN = os.environ['TWITTER_ACCESS_TOKEN']
    ACCESS_TOKEN_SECRET = os.environ['TWITTER_ACCESS_TOKEN_SECRET']

    # APIクライアントを取得する
    client = tweepy.Client(
                bearer_token=BEARER_TOKEN,
                consumer_key=API_KEY, consumer_secret=API_KEY_SECRET,
                access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET,
                )
    return client


def get_tweets_count(client, query, end_time, start_time, granularity):
    try:
        counts = client.get_recent_tweets_count(
                            query, 
                            end_time = end_time,
                            start_time = None if start_time is None else start_time,
                            granularity = granularity
                            )
    except Exception as e:
        print(e)
        return None
    
    for i, item in enumerate(counts.data):
        # [:-5]はミリセカンドの部分を削除するため
        start = datetime.datetime.fromisoformat(item['start'][:-5])
        start += TIME_DELTA # 時刻をJSTに変換
        end = datetime.datetime.fromisoformat(item['end'][:-5])
        end += TIME_DELTA # 時刻をJSTに変換

        if (i % 10 == 0 and granularity == 'minute'): print('')

        mark = ' ' if item['tweet_count'] == 0 else '*'
        print(f"[{i:02d} {mark}] {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} : [Tweet Counts: {item['tweet_count']}]")
        #print(f"[{i:02d}] {start:%Y-%m-%d %H:%M:%S} -> {end:%Y-%m-%d %H:%M:%S} : [Tweet Counts: {item['tweet_count']}]")

    return counts

def get_tweets_text(client, query, end_time, start_time, max_counts=3000):
    tweet_list = []
    next_token = None
    tweet_counts = 0

    while True:
        try:
            tweets = client.search_recent_tweets(
                                query, 
                                end_time = end_time,
                                start_time = start_time,
                                expansions = ['author_id','referenced_tweets.id'],
                                tweet_fields = ['created_at','referenced_tweets'], 
                                user_fields = ['verified'], 
                                max_results = 100,
                                next_token = next_token
                                )
        except Exception as e:
            print(e)
            return None
    
        if tweets.meta["result_count"] == 0: break
        if tweets.data is None: return None
    
        for i, item in enumerate(tweets.data):
            user = get_user_info(tweets.includes['users'], item.author_id)

            dt = item.created_at + TIME_DELTA # 時刻をJSTに変換
            retweet = get_rt_user(item.text) if item.text.startswith('RT ') else None

            dic = {'created_at': f'{dt:%Y-%m-%d %H:%M:%S}', 
                   'user_id': user["id"],
                   'name': user["name"],
                   'username': f'@{user["username"]}',
                   'verified': user["verified"],

                   'tweet_id': item.id,

                   # リツイートを簡略表示にするか
                   'text': item.text if retweet is None else f'RT {retweet}: ～',
                   #'text': item.text,

                   'tweet_url': get_tweet_url(user["username"], item.id),
                  }

            tweet_list.append(dic)
            
            tweet_counts += 1
            if tweet_counts >= max_counts: break

        if ('next_token' in tweets.meta and tweet_counts < max_counts):
            next_token = tweets.meta['next_token']
            time.sleep(1) # １秒間待機する
        else:
            break

    return tweet_list[::-1] # 逆順にソートしてリターン


def get_user_info(users, author_id):
    for user in users:
        if user["id"] == author_id:
            return user

    assert False, 'User not found.'


def get_tweet_url(username, tweet_id):
    url = f'https://twitter.com/{username}/status/{tweet_id}'
    return url


def get_rt_user(text):
    m = RT_PATTERN.match(text)
    if m:
        return m.group(1)
    else:
        return None


def write_json_file(client, query, item):
    # 該当するツイートを取得する（[:-5]はミリセカンドの部分を削除するため）
    end_time = datetime.datetime.fromisoformat(item['end'][:-5])
    start_time = datetime.datetime.fromisoformat(item['start'][:-5])

    # とりあえず最大1000ツイートまで取得する
    tweets = get_tweets_text(client, query, end_time, start_time, 1000)
    print(f'Got {len(tweets)} tweet data.')

    # JSON形式で保存する
    filename = f'tweet_root ({query}).json'
    with open(filename, 'w', encoding="utf-8") as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False)

    print(f'"{filename}"という名前で保存しました。')
    
    return tweets


def write_json_file_ex(client, query, counts, index_range):
    tweets = []

    for index in index_range:
        item = counts.data[index]

        # 該当するツイートを取得する（[:-5]はミリセカンドの部分を削除するため）
        end_time = datetime.datetime.fromisoformat(item['end'][:-5])
        start_time = datetime.datetime.fromisoformat(item['start'][:-5])

        # とりあえず最大1000ツイートまで取得する
        temp = get_tweets_text(client, query, end_time, start_time, 1000)

        tweets.extend(temp)

    print(f'Got {len(tweets)} tweet data.')

    # JSON形式で保存する
    filename = f'tweet_root ({query}).json'
    with open(filename, 'w', encoding="utf-8") as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False)

    print(f'"{filename}"という名前で保存しました。')
    return tweets


def get_next_step():
    print(f'\nDrill down more [D] or Save tweet data [S] or Abort [A]')
    ans = input('Input command: ')
    return ans.upper()


def get_range_index(seq):
    if '..' not in seq: return None

    try:
        lst = [int(x.strip()) for x in seq.split('..')]
        if len(lst) != 2: 
            raise ValueError("Invalid range error.")

        lst.sort()
        ret = range(lst[0], lst[1] + 1)
    except ValueError as e:
        return None

    return ret


def test(client):
    resp = client.get_me()

    print(type(resp.data))
    print('id:', resp.data.id)
    print('name:', resp.data.name)
    my_user_id = resp.data.id

    resp = client.get_users_tweets(my_user_id, max_results=5)

    print(type(resp.data), type(resp.data[0]))
    print(len(resp.data), '件のツイートを取得しました')

    for i, tweet in enumerate(resp.data[:3]):
        print(f'----- {i + 1} -----')
        print(tweet.text)

    return


def main():
    client = init_twitter_api()

    #test(client)
    #return

    # 検索するハッシュタグ
    #query = '#広瀬すず'
    query = input('\nInput target text for searching trend root: ')
    #if (query[0] != '#'): query = '#' + query

    # 日付単位での検索（約７日間）
    end_time = datetime.datetime.now() - datetime.timedelta(hours = 1)
    start_time = end_time - datetime.timedelta(days = 7)

    counts = get_tweets_count(client, query, end_time - TIME_DELTA, start_time, 'day')
    if counts is None: return

    ans = input('\nInput target day index: ')
    if ans.isdigit():
        next = get_next_step()

        if (next == 'S'):
            # 該当する時間帯のツイートを保存する
            tweets = write_json_file(client, query, counts.data[int(ans)])
            return
        elif (next == 'A'):
            print('Abort process.')
            return
        elif (next != 'D'):
            print('Unknown command. Abort process.')
            return
    else:
        index_range = get_range_index(ans)

        if index_range is None:
            print('Invalid index. Abort process.')
            return
        else:
            # 該当する時間帯のツイートを保存する
            tweets = write_json_file_ex(client, query, counts, index_range)
            return

    # 時刻単位、分単位での検索
    time_scale = ['hour', 'minute']

    for unit in time_scale:
        index = int(ans)
        item = counts.data[index]

        # [:-5]はミリセカンドの部分を削除するため
        end_time = datetime.datetime.fromisoformat(item['end'][:-5])
        start_time = datetime.datetime.fromisoformat(item['start'][:-5])

        counts = get_tweets_count(client, query, end_time, start_time, unit)
        if counts is None: return

        ans = input(f'\nInput target {unit} index: ')
        if ans.isdigit():
            next = 'S' if unit == 'minute' else get_next_step()

            if (next == 'S'):
                # 該当する時間帯のツイートを保存する
                tweets = write_json_file(client, query, counts.data[int(ans)])
                return
            elif (next == 'A'):
                print('Abort process.')
                return
            elif (next != 'D'):
                print('Unknown command. Abort process.')
                return
        else:
            index_range = get_range_index(ans)

            if index_range is None:
                print('Invalid index. Abort process.')
                return
            else:
                # 該当する時間帯のツイートを保存する
                tweets = write_json_file_ex(client, query, counts, index_range)
                return


if __name__ == '__main__':
    main()
