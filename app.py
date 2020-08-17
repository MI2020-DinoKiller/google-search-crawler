import re
import time
import sys
import requests
import json
import jieba
import zhconv  # 简体繁体转换
import urllib.parse
from bs4 import BeautifulSoup, Comment
from fake_useragent import UserAgent
import pymysql  # 链接sql资料库
from jieba.analyse import *

print("正在分析 config.json 檔案...")
input_file = open('config.json')
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


def insert_into_search(searchstring):

    sql = "select SearchId from search where SearchString ='"+searchstring+"'"
    #需要先执行sql语句
    if cursor.execute(sql):
        #得到返回值jilu,jilu是一个元组
        jilu = cursor.fetchone()
        #通过下标取出值即可
        print('已有相同搜寻,对应的id是：', jilu['SearchId'])
    else:
        print('没有对应的搜寻，新增中。。。。')
        insert_color = ("INSERT INTO search(SearchString)" "VALUES(%s)")
        dese = (searchstring)
        cursor.execute(insert_color, dese)
        db.commit()
        print("新增完成！")


def find_searchId(searchstring):
    sql = "select SearchId from search where SearchString ='" + searchstring + "'"
    # 需要先执行sql语句
    if cursor.execute(sql):
        # 得到返回值jilu,jilu是一个元组
        jilu = cursor.fetchone()
        # 通过下标取出值即可
        Id = jilu['SearchId']
        return (Id)


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
    return (Id)


def insert_into_searchresult(Link,Title,Content,searchstring):
    Id=find_searchId(searchstring)
    #whitelistid=find_white_id(Link)
    insert_color = ("INSERT INTO searchresult(Link,Title,Content,SearchId)" "VALUES(%s,%s,%s,%s)")
    dese = (Link,Title,Content,Id)
    cursor.execute(insert_color, dese)
    db.commit()


x = sys.argv[1]
x = zhconv.convert(x, 'zh-tw')  # 简体转换繁体
words = jieba.lcut_for_search(x)
x = zhconv.convert(x, 'zh-hans')
for i in jieba.lcut_for_search(x):
    words.append(i)  # 分割搜寻字串
print(words)
y = sys.argv[2]
y = int(y)
y = (y - 1) * 10 + 1
z=input("取多少字串：")
z=int(z)


def get_key_words(x):
    tags2 = jieba.analyse.extract_tags(x, topK=3, withWeight=False)
    return tags2


def cut_all(output, x):
    print("\n关键句直接切：\n")
    cuts = []
    for i in range(1, 5):
        for j in range(len(x) - i + 1):
            x = x.encode('utf-8').decode("utf-8")
            w = x[j:j + i]
            cuts.append(w)
    print("\n", cuts)
    c = []  # 储存关键词位置
    for i in cuts:
        start = 0
        while (output.find(i, start) != -1):
            c.append(output.find(i, start))
            start = output.find(i, start) + 1
    c = list(set(c))
    c.sort()
    print("\n", c, "\n")
    is_choiced = 0
    for j in range(len(c) - 1):
        if c[j + 1] - c[j] <= z:
            is_choiced = 1
            print(output[c[j]:c[j] + z])
        elif (is_choiced == 0):
            print(output[c[j] - int(z / 2):c[j] + int(z / 2)])
        else:
            is_choiced = 0


def jieba_cut(output, key_words):
    cut_result = jieba.lcut(output)
    cut_result.remove(' ')
    words_number = []
    index = []
    print("\n全模式\n：" + "|".join(cut_result))
    for w in key_words:
        n = 0
        for i in range(len(cut_result)):
            if cut_result[i] == w:
                n += 1
                index.append(i)
        words_number.append(n)
    print("\n", words, words_number)

    for i in range(len(index) - 1):
        juzi = ""
        if (index[i + 1] - index[i]) <= z:
            for j in range(index[i], index[i] + z):
                juzi += '{} '.format(cut_result[j])
        else:
            for j in range(index[i] - int(z / 2), index[i] + int(z / 2)):
                juzi += '{} '.format(cut_result[j])
        print("结巴切词：", juzi)


# 取得html的原始码
def get_text(link,title):
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
        #insert_into_searchresult(link, title, output, x)  # 录入search result资料表

        key_words = get_key_words(x)
        jieba_cut(output, key_words)
        cut_all(output, x)

        save = re.split(r'[。！?\s]', output)
        print("全文分割：", save, "\n")

        index = []
        data_key = []
        print("关键句筛选：")
        for i in range(len(save)):
            num = 0
            for w in words:
                num += len(re.findall(w, save[i]))
            if num > 0:
                index.append(i)
                data_key.append(save[i])
                print(save[i],"\n")
        print("\n关键句位置：", index, "\n")

        if len(index) != 0:
            print("第一个关键句位置：", index[0], "最后一个关键字位置：", index[-1], "\n")
        print("\n关键段落:")
        if len(index) > 0:
            for i in range(index[0], index[-1]):
                print(save[i])

        if len(data_key)>0:
            insert_into_searchresult(link,title,output,x)    #录入search result资料表
            print("录入资料库\n")



def google_connected(x,y,words):
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
            get_text(link,title)  # problem：google的网址可能进入pdf档；一些网址需要登入才可以预览内容，需要cookie；
t1=time.time()
for i in range(3):
    google_connected(x,i,words)
t2=time.time()
print('总共耗时：%s' % (t2 - t1))