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
    insert_color = "INSERT INTO search(SearchString) VALUES(%s)"
    dese = searchstring
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


# 取得html的原始码
def get_text(link):
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

        lecture = []
        save = []
        abandon = []
        whitelist = ['div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        text = soup.find_all(text=True)
        for i in text:
            if i.parent.name in whitelist:
                num = 0
                lecture.append(i)
                if len(lecture) % 3 == 0:
                    for l in lecture:
                        for w in words:
                            num += len(re.findall(w, str(l)))
                        if num > 0:
                            save.append(lecture)
                            break
                    lecture = []

        if len(save) > 0:
            for i in save:
                for j in i:
                    if j != '\n':
                        if len(j) > 4:
                            print(j)
        else:
            print("abandon\n\n")
            for i in text:
                if i != '\n':
                    print(i)


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
        get_text(link)  # problem：google的网址可能进入pdf档；一些网址需要登入才可以预览内容，需要cookie；
