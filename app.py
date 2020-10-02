import math
import os
import re
import json
import logging
import sys
import time
import string

import pika as pika
import pymysql
import requests
import zhconv
from serpwow.google_search_results import GoogleSearchResults
from fake_useragent import UserAgent
from bs4 import BeautifulSoup, Comment
import unicodedata


def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C" or unicodedata.category(ch)[0] != "Z")


dataPath = os.path.dirname(os.path.abspath(__file__))

logging.info("正在分析 config.json 檔案...")
input_file = open(os.path.join(dataPath, 'config.json'))
CONFIG = json.load(input_file)
logging.info("分析完畢 config.json")

# 鏈接mysql
logging.info('連接到mysql服務器...')
db = pymysql.connect(
    host=CONFIG["Database"]["host"],
    user=CONFIG["Database"]["user"],
    passwd=CONFIG["Database"]["passwd"],
    db=CONFIG["Database"]["dbname"],
    charset=CONFIG["Database"]["charset"],
    cursorclass=pymysql.cursors.DictCursor)
logging.info('連接上了!')
cursor = db.cursor()

serpwow = GoogleSearchResults(CONFIG["GSR_API_KEY"])


def insert_into_search(searchstring: str):
    sql = "SELECT `SearchId` FROM `search` WHERE `SearchString`=%s"
    # 需要先執行sql語句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一個元組
        jilu = cursor.fetchone()
        # 通過下標取出值即可
        print('已有相同搜尋,對應的id是：', jilu['SearchId'])
    else:
        print('沒有對應的搜尋，新增中。。。。')
        insert_color = "INSERT INTO `search` (`SearchString`) VALUES (%s)"
        cursor.execute(insert_color, (searchstring))
        db.commit()
        print("新增完成！")


def find_searchId(searchstring: str):
    sql = "SELECT `SearchId` FROM `search` WHERE `SearchString`=%s"
    # 需要先執行sql語句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一個元組
        jilu = cursor.fetchone()
        # 通過下標取出值即可
        ret = jilu['SearchId']
        return ret


def find_white_id(link):
    sql = "SELECT * FROM `whitelist`"
    # 需要先執行sql語句
    Id = ""
    row = cursor.fetchone()
    while row:
        print(row['WhiteListLink'])
        if len(re.findall(row['WhiteListLink'], link)):
            Id = row['WhiteListId']
        row = cursor.fetchone()
    return Id


def insert_into_searchresult(Link: str, Title: str, Content: str, searchstring: str):
    Id = find_searchId(searchstring)
    # whitelistid=find_white_id(Link)
    insert_color = "INSERT INTO searchresult(Link,Title,Content,SearchId) VALUES(%s,%s,%s,%s)"
    dese = (Link, Title, Content, Id)
    cursor.execute(insert_color, dese)
    db.commit()


# 使用Google的搜尋結果數量來當idf
def find_idf(string):
    # urls = '{}cx={}&key={}&q="{}"'.format(CONFIG["google_search_api_url"],
    #                                       CONFIG["google_search_api_cx"],
    #                                       CONFIG["google_search_api_key"], urllib.parse.quote_plus(string))
    # data = requests.get(urls).json()
    my_params = {
        "cx": CONFIG["google_search_api_cx"],
        "key": CONFIG["google_search_api_key"],
        "q": string
    }
    data = requests.get(CONFIG["google_search_api_url"], my_params).json()
    result = data.get("searchInformation")
    result_number = result.get("totalResults")
    return result_number


def idf_detected(searchstring):
    sql = "SELECT `idfnumber` FROM `idf` WHERE `idfstring`=%s"
    # 需要先執行sql語句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一個元組
        jilu = cursor.fetchone()
        # 通過下標取出值即可
        return jilu['idfnumber']
    else:
        print('沒有對應的搜尋，新增中。。。。')
        number = find_idf(searchstring)
        insert_color = "INSERT INTO `idf`(`idfstring`, `idfnumber`) VALUES (%s, %s)"
        dese = (searchstring, number)
        cursor.execute(insert_color, dese)
        db.commit()
        print("新增完成！")
        return number


def count_idf(c):
    if len(c) != 0:
        total = 0
        num = []
        for i in c:
            n = idf_detected(i)
            total += int(n)
            num.append(n)
        idf = []
        for i in range(len(num)):
            idf.append(math.log(total / (int(num[i]) + 1)))
            print(c[i], ":", idf[i])
        return idf


def sort(sentence, grade):
    s_g = []
    for s in range(len(grade)):
        s_g.append([sentence[s], grade[s]])
    s_g = sorted(s_g, key=lambda sl: (sl[1]), reverse=True)
    for i in s_g:
        if (i[1] / sum_idf) >= 0.5:
            print(i[0], ":", i[1] / sum_idf, "\n")


def get_idf_sentence(c, idf, sentence):
    grade = []
    for s in sentence:
        g = 0
        for i in range(len(c)):
            if s.find(c[i]) != -1:
                g += idf[i]
        grade.append(g)
    sort(sentence, grade)


def cut(x):
    # 人工切詞
    cuts = []
    for j in x:
        cuts.append(j)
    return cuts


def cut_all(output, cuts):
    c = []  # 儲存關鍵詞位置
    for i in cuts:
        start = 0
        while (output.find(i, start) != -1):
            c.append(output.find(i, start))
            start = output.find(i, start) + 1
    c = list(set(c))
    c.sort()
    print("\n", c, "\n")
    if len(c) != 0:
        sentence = []
        start = c[0]  # 初始位置
        end = 0
        print("[")
        for j in range(1, len(c)):
            if c[j] - start <= z:
                end = c[j]
            else:
                while output[start] != '。' and output[start] != '!' and output[start] != '?' and output[start] != ' '\
                        and output[start] != '？' and output[start] != '！':
                    start -= 1
                while output[end] != '。' and output[end] != '!' and output[end] != '?' and output[end] != ' ' and \
                        output[end] != '？' and output[end] != '！':
                    end += 1
                # 去除重复句子
                last_str = ''
                for s in output[start + 1:end]:
                    if s != '。' and s != '!' and s != '?' and s != ' ' and s != '？' and s != '！':
                        last_str += s
                    else:
                        break
                if len(sentence) > 0:
                    if sentence[-1].find(last_str) != -1:
                        start += len(last_str) + 1
                result = output[start + 1:end].strip()
                result = result.translate(str.maketrans('', '', string.whitespace))
                result = remove_control_characters(result)

                if result != "":
                    sentence.append(result)
                    print("\"", result, "\",", sep='')

                start = c[j]
        print("]")
        get_idf_sentence(cuts, idf, sentence)
        return sentence


def get_text(link, title):
    headers = {
        'Host': 'ptlogin2.qq.com',
        "User-Agent": UserAgent(verify_ssl=False).random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-CN;q=0.8,en;q=0.7',
        'Connection': 'keep-alive'
    }  # useragent反爬
    try:
        res = requests.get(link, headers)
    except Exception as e:
        print(e)  # 輸出異常行為名稱
    else:
        html_page = res.content
        soup = BeautifulSoup(html_page, 'html.parser')  # beautifulsoup抓取網頁源代碼

        comments = soup.findAll(text=lambda func_text: isinstance(func_text, Comment))  # 去除網頁內的註解
        [comment.extract() for comment in comments]

        save = []
        output = ''
        text = soup.find_all(text=True)
        blacklist = [
            'a',
            'abbr',
            'body',
            'button',
            'caption',
            'cite',
            'footer',
            'form',
            'head',
            'html',
            'i',
            'label',
            'li',
            'link',
            'ol',
            'nav',
            'option',
            'script',
            'small',
            'section',
            'select',
            'style',
            'sub',
            'sup',
            'svg',
            'title',
            'table',
            'tbody',
            'th',
            'ul'

            # there may be more elements you don't want, such as "style", etc.
        ]

        for t in text:
            if t.parent.name not in blacklist:
                if len(t) > 4:
                    output += '{}'.format(t.strip())
        # print("全部的text：\n", output)
        # insert_into_searchresult(link, title, output, x)  # 錄入search result資料表

        ret = cut_all(output, x)
        print(ret)
        return ret


def google_connected(x, y):
    params = {
        'api_key': CONFIG["GSR_API_KEY"],
        'q': x,
        'gl': 'tw',
        'hl': 'zh-tw',
        'location': 'Taiwan',
        'num': y,
        'google_domain': 'google.com.tw',
        'output': 'json',
        'lr': 'lang_zh-TW'
    }
    # make the http GET request to Scale SERP
    api_result = requests.get('https://api.scaleserp.com/search', params)
    data = api_result.json()
    # print(json.dumps(data))
    # get the result items
    search_items = data.get("organic_results")
    if search_items is None:
        print("無相關資料！")  # 是否有搜尋到資料
    else:
        # iterate over 10 results found
        for i, search_item in enumerate(search_items):
            # get the page title
            title = search_item.get("title")
            # page snippet
            snippet = search_item.get("snippet")
            # extract the page url
            link = search_item.get("link")
            # print the results
            print("=" * 10, f"Result #{i}", "=" * 10)
            print("Description:", snippet)
            print("URL:", link, "\n")
            ret = get_text(link, title)  # problem：google的網址可能進入pdf檔；一些網址需要登入才可以預覽內容，需要cookie；


x = sys.argv[1]
x = x.replace(" ", "")
insert_into_search(x)
print("\n關鍵句直接切：\n")
cuts = cut(x)
for i in cut(x):
    if i not in cuts:
        cuts.append(i)
print("\n", cuts)
idf = count_idf(cuts)
sum_idf = 0
for i in idf:
    sum_idf += i
y = 30
z = 150
t1 = time.time()
google_connected(x, y)
t2 = time.time()
print('總共耗時：%s' % (t2 - t1))
