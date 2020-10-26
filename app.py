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

logging.info('Connecting RabbitMQ......')
connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=CONFIG["RABBITMQ"]["HOST"]))
channel = connection.channel()
channel.queue_declare(queue=CONFIG["RABBITMQ"]["QUEUE"], durable=True)
logging.info('Connected RabbitMQ Success!')

# 鏈接mysql
logging.info('Connecting MySQL Server...')
db = pymysql.connect(
    host=CONFIG["Database"]["host"],
    user=CONFIG["Database"]["user"],
    passwd=CONFIG["Database"]["passwd"],
    db=CONFIG["Database"]["dbname"],
    charset=CONFIG["Database"]["charset"],
    cursorclass=pymysql.cursors.DictCursor)
logging.info('Connected MySQL Server Success!')
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
def find_idf(string: str):
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
        for counter in c:
            n = idf_detected(counter)
            total += int(n)
            num.append(n)
        re_idf = []
        for counter in range(len(num)):
            re_idf.append(math.log(total / (int(num[counter]) + 1)))
            print(c[counter], ":", re_idf[counter])
        return re_idf


def sort(sentence, grade):
    s_g = []
    for s in range(len(grade)):
        s_g.append([sentence[s], grade[s]])
    s_g = sorted(s_g, key=lambda sl: (sl[1]), reverse=True)
    ret = []
    for counter in s_g:
        if ((counter[1] / idf_sum) >= 0.5 or counter[1]>=first_six) and len(counter[0]) < 500:
            ret.append(counter[0])
            print(counter[0], ":", counter[1] / idf_sum, "\n")
    return ret


def get_idf_sentence(c, idf, sentence):
    grade = []
    for s in sentence:
        g = 0
        for counter in range(len(c)):
            if s.find(c[counter]) != -1:
                g += idf[counter]
        grade.append(g)
    ret = sort(sentence, grade)
    return ret


def cut(x):
    # 人工切詞
    ret_cut = []
    for j in x:
        ret_cut.append(j)
    return ret_cut


def cut_all(output, cuts):
    c = []  # 儲存關鍵詞位置
    for i in cuts:
        start = 0
        while (output.find(i, start) != -1):
            c.append(output.find(i, start))
            start = output.find(i, start) + 1
    c = list(set(c))
    c.sort()
    # print("\n", c, "\n")
    if len(c) != 0:
        sentence = []
        start = c[0]  # 初始位置
        end = 0
        for j in range(1, len(c)):
            if c[j] - start <= TEXT_LIMIT:
                end = c[j]
            else:
                while output[start] != '。' and output[start] != '!' and output[start] != '?' and output[start] != ' ' \
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
                start = c[j]
        sentences = get_idf_sentence(cuts, idf, sentence)
        return sentences


def get_text(link, title):
    headers = {
        'Host': 'ptlogin2.qq.com',
        "User-Agent": UserAgent(verify_ssl=False).random,  # useragent反爬
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive'
    }
    try:
        res = requests.Session().head(link, timeout=30, headers=headers)
        content_type = res.headers["content-type"]
        if content_type != "application/pdf":
            res = requests.get(link, headers)
        else:
            return []
    except Exception as e:
        logging.error("%s", e)
    else:
        html_page = res.content
        soup = BeautifulSoup(html_page, 'html.parser')  # beautifulsoup抓取網頁源代碼

        comments = soup.findAll(text=lambda func_text: isinstance(func_text, Comment))  # 去除網頁內的註解
        [comment.extract() for comment in comments]

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
                    output += '{}'.format(t)
        # 去除襍訊
        # 頭部
        d = 0
        delete = ''
        for j in range(50):
            for i in range(len(output)):
                if output[i] != '。' and output[i] != '!' and output[i] != '?' and output[i] != ' ' and \
                        output[i] != '？' and output[i] != '！':
                    delete += '{}'.format(output[i])
                else:
                    break
            for w in searchText:
                if delete.find(w) != -1:
                    d = 1
            if d == 0:
                output = output[len(delete) + 1:]
                delete = ''
            else:
                break

        # 尾部
        if len(output) != 0:
            if output[-1] != '。' and output[-1] != '!' and output[-1] != '?' and output[-1] != '？' and \
                    output[-1] != '！':
                buttom = len(output)
                for i in reversed(range(len(output))):
                    if output[i] != '。':
                        buttom = i
                    else:
                        break
                output = output[:buttom]
            # print(output)

        # insert_into_searchresult(link, title, output, x)  # 錄入search result資料表
        ret = cut_all(output, searchText)
        return ret


def google_connected(keywords, number):
    params = {
        'api_key': CONFIG["GSR_API_KEY"],
        'q': keywords,
        'gl': 'tw',
        'hl': 'zh-tw',
        'location': 'Taiwan',
        'num': number,
        'google_domain': 'google.com.tw',
        'output': 'json',
        'lr': 'lang_zh-TW'
    }
    # make the http GET request to Scale SERP
    api_result = requests.get('https://api.scaleserp.com/search', params)
    data = api_result.json()
    search_items = data.get("organic_results")
    if search_items is None:
        print("無相關資料！")  # 是否有搜尋到資料
    else:
        for counter, search_item in enumerate(search_items):
            title = search_item.get("title")
            snippet = search_item.get("snippet")
            link = search_item.get("link")
            print("=" * 10, f"Result #{counter}", "=" * 10)
            print("Description:", snippet)
            print("URL:", link, "\n")
            ret = get_text(link, title)  # problem：google的網址可能進入pdf檔；一些網址需要登入才可以預覽內容，需要cookie；
            # idf_words = set()
            SendToRabbitMQ({"sentence": ret, "idf_words": cuts, "idf_dict": idf_dict, "idf_sum": idf_sum, "url": link})


def SendToRabbitMQ(message: dict):
    print(message)
    message = json.dumps(message)
    channel.basic_publish(
        exchange='',
        routing_key=CONFIG["RABBITMQ"]["QUEUE"],
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)  # make message persistent
    )


searchText = sys.argv[1]
insert_into_search(searchText)

cuts = cut(searchText)  # 切出關鍵句
idf = count_idf(cuts)
idf_sum = 0.0
for i in idf:
    idf_sum += i
#取前六個idf的總和
cuts_idf=[]
for i in range(len(idf)):
    cuts_idf.append([cuts[i],idf[i]])
cuts_idf= sorted(cuts_idf,key=lambda sl: (sl[1]),reverse=True)
first_six=0
if len(cuts)>=6:
    for i in range(6):
        first_six+=cuts_idf[1][i]

print(first_six)
idf_dict = {c: idf[counter] for counter, c in enumerate(cuts)}
searchResultLimit = 30
TEXT_LIMIT = 150
t1 = time.time()
google_connected(searchText, searchResultLimit)
t2 = time.time()
print('總共耗時：%s' % (t2 - t1))

# url2 = ["http://www.bcc.com.tw/newsView.4059191",
#         "https://www.hk01.com/%E5%8D%B3%E6%99%82%E5%9C%8B%E9%9A%9B/448819/%E6%96%B0%E5%86%A0%E8%82%BA%E7%82%8E-%E7%91%9E%E5%85%B8%E5%B0%88%E5%AE%B6%E6%94%AF%E6%8C%81%E8%8B%B1%E5%9C%8B-%E7%BE%A4%E9%AB%94%E5%85%8D%E7%96%AB-%E6%A6%82%E5%BF%B5",
#         "https://www.commonhealth.com.tw/article/article.action?nid=81158",
#         "http://www.healthnews.com.tw/news/article/45519"]
# for url in url2:
#     result_text = get_text(url, "")
#     SendToRabbitMQ({"sentence": result_text, "idf_words": cuts, "idf_dict": idf_dict, "idf_sum": idf_sum, , "url": url})
