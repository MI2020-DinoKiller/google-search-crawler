import re
import time
import sys
import requests
import json
import jieba
import zhconv  #简体繁体转换
import urllib.parse
from bs4 import BeautifulSoup, Comment
from fake_useragent import UserAgent

print("正在分析 config.json 檔案...")
input_file = open('config.json')
GSA = json.load(input_file)
print("分析完畢 config.json")

x = sys.argv[1]
x=zhconv.convert(x, 'zh-tw') #简体转换繁体
words=jieba.lcut_for_search(x)
x=zhconv.convert(x, 'zh-hans')
for i in jieba.lcut_for_search(x):
    words.append(i) # 分割搜寻字串
y = sys.argv[2]
y = int(y)
y = (y - 1) * 10 + 1


# 取得html的原始码
def get_text(link):
    time.sleep(0.5)  # 解决'Connection aborted.'问题，是否是因为访问频率被阻挡
    headers = {
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

        abandon = []
        index = 0
        location = []
        result = soup.find_all('p', text=True)
        for i in result:
            num = 0
            for w in words:
                if len(re.findall(w, str(i))) > 0:
                    num += len(re.findall(w, str(i)))
            if num > 0:
                location.append(index)
            index += 1
        output = ''
        if len(location) > 0:
            for i in range(location[0], location[-1]):
                output += '{} '.format(result[i])
            for i in range(0, location[0]):
                abandon.append(result[i])
            for i in range(location[-1], index):
                abandon.append(result[i])
        pattern = re.compile(r'<[^>]+>', re.S)  # 去除tag键
        result = pattern.sub('', output)
        print(result)
        print("\n\n\n", abandon)


urls = '{}cx={}&key={}&q="{}"&start={}'.format(GSA["google_search_api_url"],
                                               GSA["google_search_api_cx"],
                                               GSA["google_search_api_key"], urllib.parse.quote_plus(x), y)
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
