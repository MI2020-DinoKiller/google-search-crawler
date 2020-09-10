import re
import time
import sys
import requests
import json
import zhconv  # 简体繁体转换
import urllib.parse
from bs4 import BeautifulSoup, Comment
from fake_useragent import UserAgent
import pymysql  # 链接sql资料库
import math
import os

dataPath = os.path.dirname(os.path.abspath(__file__))

print("正在分析 config.json 檔案...")
input_file = open(os.path.join(dataPath, 'config.json'))
CONFIG = json.load(input_file)
print("分析完畢 config.json")

# 链接mysql
print('连接到mysql服务器...')
db = pymysql.connect(
    host=CONFIG["Database"]["host"],
    user=CONFIG["Database"]["user"],
    passwd=CONFIG["Database"]["passwd"],
    db=CONFIG["Database"]["dbname"],
    charset=CONFIG["Database"]["charset"],
    cursorclass=pymysql.cursors.DictCursor)
print('连接上了!')
cursor = db.cursor()


def insert_into_search(searchstring: str):
    sql = "SELECT `SearchId` FROM `search` WHERE `SearchString`=%s"
    # 需要先执行sql语句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一个元组
        jilu = cursor.fetchone()
        # 通过下标取出值即可
        print('已有相同搜寻,对应的id是：', jilu['SearchId'])
    else:
        print('没有对应的搜寻，新增中。。。。')
        insert_color = "INSERT INTO `search` (`SearchString`) VALUES (%s)"
        cursor.execute(insert_color, (searchstring))
        db.commit()
        print("新增完成！")


def find_searchId(searchstring: str):
    sql = "SELECT `SearchId` FROM `search` WHERE `SearchString`=%s"
    # 需要先执行sql语句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一个元组
        jilu = cursor.fetchone()
        # 通过下标取出值即可
        ret = jilu['SearchId']
        return ret


def find_white_id(link):
    sql = "select * from whitelist"
    # 需要先执行sql语句
    Id = ""
    row = cursor.fetchone()
    while row:
        print(row['WhiteListLink'])
        if len(re.findall(row['WhiteListLink'], link)):
            Id = row['WhiteListId']
        row = cursor.fetchone()
    return Id


def insert_into_searchresult(Link, Title, Content, searchstring):
    Id = find_searchId(searchstring)
    # whitelistid=find_white_id(Link)
    insert_color = "INSERT INTO searchresult(Link,Title,Content,SearchId) VALUES(%s,%s,%s,%s)"
    dese = (Link, Title, Content, Id)
    cursor.execute(insert_color, dese)
    db.commit()


# 使用Google的搜寻结果数量来当idf
def find_idf(string):
    urls = '{}cx={}&key={}&q="{}"'.format(CONFIG["google_search_api_url"],
                                          CONFIG["google_search_api_cx"],
                                          CONFIG["google_search_api_key"], urllib.parse.quote_plus(string))
    data = requests.get(urls).json()
    result = data.get("searchInformation")
    result_number = result.get("totalResults")
    return result_number


def idf_detected(searchstring):
    sql = "SELECT `idfnumber` FROM `idfh` WHERE `idfstring`=%s"
    # 需要先执行sql语句
    if cursor.execute(sql, (searchstring)):
        # 得到返回值jilu,jilu是一个元组
        jilu = cursor.fetchone()
        # 通过下标取出值即可
        print('已有相同搜寻,对应的idf分值是：', jilu['idfnumber'])
        return jilu['idfnumber']
    else:
        print('没有对应的搜寻，新增中。。。。')
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
    s_g = sorted(s_g, key=lambda sl: (sl[1]))
    for i in s_g:
        print(i[0], ":", i[1] / sum_idf, "\n")


def get_idf_sentence(c, idf, sentence):
    grade = []
    for s in sentence:
        g = 0
        for i in range(len(c)):
            if s.find(c[i]) != 0:
                g += idf[i]
        grade.append(g)
    sort(sentence, grade)


def cut(x):
    # 人工切词
    cuts = []
    for i in range(1, 3):
        for j in range(len(x) - i + 1):
            w = x[j:j + i]
            cuts.append(w)
    return cuts


def cut_all(output, cuts):
    c = []  # 储存关键词位置
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
        for j in range(1, len(c)):
            if c[j] - start <= z:
                end = c[j]
            else:
                while output[start] != '。' and output[start] != '!' and output[start] != '?' and output[
                    start] != ' ' and output[start] != '？' and output[start] != '！':
                    start -= 1
                while output[end] != '。' and output[end] != '!' and output[end] != '?' and output[end] != ' ' and \
                        output[end] != '？' and output[end] != '！':
                    end += 1
                print("(", output[start + 1:end], ")")
                sentence.append(output[start + 1:end])
                start = c[j]
        get_idf_sentence(cuts, idf, sentence)


x = sys.argv[1]
x = x.replace(" ", "")
insert_into_search(x)
x = zhconv.convert(x, 'zh-tw')  # 简体转换繁体
print("\n关键句直接切：\n")
cuts = cut(x)
x = zhconv.convert(x, 'zh-hans')
for i in cut(x):
    if i not in cuts:
        cuts.append(i)
print("\n", cuts)
idf = count_idf(cuts)
sum_idf = 0
for i in idf:
    sum_idf += i
y = sys.argv[2]
y = int(y)
y = (y - 1) * 10 + 1
z = 120


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
        print(e)  # 输出异常行为名称
    else:
        html_page = res.content
        soup = BeautifulSoup(html_page, 'html.parser')  # beautifulsoup抓取网页源代码

        comments = soup.findAll(text=lambda text: isinstance(text, Comment))  # 去除网页内的注解
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
            'strong',
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
                    output += '{} '.format(t)
        print("全部的text：\n", output)
        # insert_into_searchresult(link, title, output, x)  # 录入search result资料表

        cut_all(output, x)

        save = re.split(r'[。！?\s]', output)
        print("全文分割：", save, "\n")


def google_connected(x, y):
    urls = '{}cx={}&key={}&q="{}"&start={}'.format(CONFIG["google_search_api_url"],
                                                   CONFIG["google_search_api_cx"],
                                                   CONFIG["google_search_api_key"], urllib.parse.quote_plus(x), y)
    data = requests.get(urls).json()
    # get the result items
    search_items = data.get("items")
    if search_items is None:
        print("无相关资料！")  # 是否有搜寻到资料
    else:
        # iterate over 10 results found
        for i, search_item in enumerate(search_items, start=y):
            # get the page title
            title = search_item.get("title")
            # page snippet
            snippet = search_item.get("snippet")
            # alternatively, you can get the HTML snippet (bolded keywords)
            html_snippet = search_item.get("htmlSnippet")
            # extract the page url
            link = search_item.get("link")
            # print the results
            print("=" * 10, f"Result #{i}", "=" * 10)
            print("Description:", snippet)
            print("URL:", link, "\n")
            get_text(link, title)  # problem：google的网址可能进入pdf档；一些网址需要登入才可以预览内容，需要cookie；


t1 = time.time()
for i in range(3):
    google_connected(x, i)
t2 = time.time()
print('总共耗时：%s' % (t2 - t1))
