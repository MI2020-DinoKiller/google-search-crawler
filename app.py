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


def insert_into_searchresult(Link, Title, Content, searchstring):
    Id = find_searchId(searchstring)
    whitelistid = find_white_id(Link)
    insert_color = ("INSERT INTO searchresult(Link,Title,Content,SearchId,WhiteListId)" "VALUES(%s,%s,%s,%s,%s)")
    dese = (Link, Title, Content, Id, whitelistid)
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
        insert_into_searchresult(link, title, output, x)  # 录入search result资料表

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
                print(save[i])
        print("\n关键句位置：", index, "\n")

        if len(index) != 0:
            print("第一个关键句位置：", index[0], "最后一个关键字位置：", index[-1], "\n")
        print("\n关键段落:")
        if len(index) > 0:
            for i in range(index[0], index[-1]):
                print(save[i])


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
