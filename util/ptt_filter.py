'''
Modify from
https://github.com/zake7749/PTT-Chat-Generator

Some function are used to generate training corpus of the chatbot
'''

import json
import logging
import os
import jieba
import sys
import operator
from tqdm import tqdm
import pickle
import re
dict_path = os.path.join(os.getenv("JIEBA_DATA"), "dict.txt.big") 
ptt_path = (os.getenv("DATA"))
jieba.set_dictionary(dict_path)
process_files = ['Gossiping', 'Boy-Girl']
marker = {'Gossiping': '>', 'NBA': '<', 'Boy-Girl': '^'}


#count_response = {}

def main():

    Filter = ArticleFilter()

def print2file(f, title, responses, marker = '', separater = True):
    if marker != '':
        f.write(marker + ' ')
    title_cutted = jieba.cut(title.strip(), cut_all=False)
    for word in title_cutted:
        f.write(word + ' ')
    f.write('\n')
    for response in responses:
        #print(response['Content'])
        #if response['Content'] not in count_response.keys():
        #    count_response[response['Content']] = 0
        #count_response[response['Content']] += 1
        if marker != '':
            f.write(marker + ' ')
        response_cutted = jieba.cut(response['Content'].strip(), cut_all=False)
        for word in response_cutted:
            f.write(word + ' ')
        f.write('\n')
    if separater:
        f.write('===\n')

class ArticleFilter(object):

    def __init__(self):

        self.stopwords = None
        self.stoptags = None
        self.raw_data = None
        self.corpus = []
        self.order_response = []
        self.order_titles = []

        self.total_article = 0
        self.article_count = 0

        self.titles = set()
        self.users_info = {}

        self.init_load_stopwords()
        self.url_pattern = '(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9]\.[^\s]{2,})'
        logging.basicConfig(format='%(asctime)s : %(threadName)s : %(levelname)s : %(message)s', level=logging.INFO)

    def init_load_stopwords(self):
        """
        Initialize the stopwords
        """
        with open(os.path.join(ptt_path, 'stopwords/drop_comment.txt'),'r', encoding='utf-8') as sw:
            self.dropwords = [word.strip('\n') for word in sw]
        with open(os.path.join(ptt_path,'stopwords/chinese_sw.txt'), 'r', encoding='utf-8') as sw:
            self.stopwords = [word.strip('\n') for word in sw]
        with open(os.path.join(ptt_path,'stopwords/stopwords-tw.txt'), 'r', encoding='utf-8') as sw:
            self.stopwords += [word.strip('\n') for word in sw]
        with open(os.path.join(ptt_path, 'stopwords/specialMarks.txt'), 'r', encoding='utf-8') as sw:
            self.special_markers = [word.strip('\n') for word in sw]
        with open(os.path.join(ptt_path, 'stopwords/gossiping.tag'),'r', encoding='utf-8') as sw:
            self.stoptags = [word.strip('\n') for word in sw]

    def process_raw_data(self, path, is_dir=False, to_one_file=False, one_file_name="corpus.json", marker=''):

        data = []
        total = []
        filename = None
        count = 0

        if is_dir:
            filenames = [name for name in os.listdir(path) if not name.startswith(".")]
        else:
            filenames = [path]
        
        for filename in filenames:
            count +=1
            if count % 10 == 0:
                logging.info("已處理 %d 頁文章, 其中有效文章數為 %d, 總共有 %d" % (count, self.article_count, self.total_article))
            with open(os.path.join(path, filename),'r', encoding="utf-8") as data:
                res = self.generate_corpus(json.load(data), marker=marker)

    def generate_corpus(self, articles, drop_response=True, negative_tag=None, no_content=True, min_length=1, marker='', stopwords=False):

        """
        依據需求挑選出符合語料庫需求的文章

        Args:
            - articles: 描述文章的字典，格式參見 PTT-Crawler
            - drop_response: 是否濾除回應文章
            - negative_tag: 要濾除的標籤集
            - no_content: 是否需要保存文章內容
            - min_length: 只保存長度超過 min_length 之標題
        Return:
            - coprus: 一個儲存符合需求的文章列表
        """

        if negative_tag is None:
            negative_tag = self.stoptags

        clean_article = []
        for article in tqdm(articles):
            #####################濾除非結構化文章#####################
            self.total_article += 1
            try:
                title = article["Title"]
                clean_responses = self.clean_responses(article["Responses"], stopwords=stopwords)
                if len(clean_responses) == 0:
                    continue # 不需要沒有回應的文章
                article["Responses"] = clean_responses
            except Exception as e:
                #print("Wrong Format: %s" % str(e))
                continue
            ######################文章客製化選項######################
            if title in self.titles or len(title) < min_length:
                #捨去已存在語料庫的標題或過短的標題
                continue

            if drop_response:
                #捨去回應類文章與快訊文章, i.e Re: and Fw:
                if title.startswith("Re") or title.startswith("Fw"):
                    continue


            #if no_content:
            #    article.pop("Content")
            #######################標籤抽取##########################
            tag, clean_title = self.get_tag(title) #將標題與標籤分開
            # clean special markers
            for w in self.special_markers:
                clean_title = clean_title.replace(w, ' ')
            article["Tag"]   = tag
            article["Title"] = clean_title

            if tag == '新聞':
                clean_content = self.clean_news(article['Content'])
            else:
                clean_content = self.clean_content(article['Content'], split_line=False)
            article['Raw'] = article['Content']
            article['Content'] = clean_content
            self.titles.add(clean_title)
            self.order_titles.append(clean_title)
            self.order_response.append(clean_responses)

            self.article_count += 1
            clean_article.append(article)
        return clean_article

    def get_url(self, content):
        urls = re.findall(self.url_pattern, content)
        urls = [u.strip('/') for u in urls]
        return urls

    def clean_content(self, content, split_line=True):
        '''
        clean the article content
        Args:
            content: string, the article content
            split_line: whether to split the content line by line
        Return:
            cleaned_content: string
        '''
        # clean the multiple change line
        content = re.sub('\n+', '\n', content) 
        # clean the url
        content = re.sub(self.url_pattern, '', content)
        # clean the RE pattern
        content = re.sub('引述.*?之銘言', '', content)
        content = re.sub('^:.*?\n ', '', content)
        # clean FB article
        content = re.sub('ＦＢ.*?：', '', content)
        # clean the special marker
        content = re.sub('^※.*?\n', '', content)
        content = re.sub('[:：]', ' ', content)
        # clean html tag
        content = re.sub('<.*?>', '', content)
        content = re.sub('\[.*?\]', '', content)
        content = re.sub('\/.*?\/', '', content)
 
        # clean the non-chinese word (may be useful?)
        #content = re.sub('[”“.,?:\ ][a-z0-9A-Z\ ]+[”“.,?:\ ]', ' ', content)
        # clean the puncatuations
        if split_line:
            content = re.sub('[\ ，。]+', '\n', content)
            content = re.sub('[.、（]+\n', '\n', content)
        else:
            content = re.sub('[\ ，。]+', ' ', content)
            content = re.sub('[.、（]+\ ', ' ', content)

        for w in self.special_markers:
            content = content.replace(w, ' ') 
        return content.strip()

    def clean_news(self, content):
        '''
        Try to parse the news article
        still need much improvement....
        Args:
            content: string, news article content
        Return:
            news_content: string
        '''
        paragraph_tag = ['1.媒體來源:', '2.完整新聞標題:', '3.完整新聞內文:', '4.完整新聞連結 (或短網址):']
        try:
            source, content = content.split(paragraph_tag[1], 1)
            source = source.split(paragraph_tag[0], 1)[1]
            news_title, content = content.split(paragraph_tag[2], 1)
            news_content, content = content.split(paragraph_tag[3], 1)
            #print('source : ', source.strip())
            #print('title : ', news_title.strip())
            #print('content :', news_content.strip())
            return self.clean_content(news_content, split_line=False)
        except:
            return ''

    def clean_responses(self, responses, negative_user=set(), min_length=5, dropwords=None,stopwords=False):

        """
        依照負面使用者案例、回應長度與是否包含停用詞來濾除負面的回應

        Args:
            - responses: 回應的 dictionary
            - negative_user: 要濾除該 User set 的回應
            - min_length: 濾除低於 min_length 的回應
            - stopwords: 濾除有敏感字詞的回應
        Return:
            - Responses: 已清除負面回應的字典
        """

        if dropwords is None:
            dropwords = self.dropwords
        if stopwords:
            stopwords = self.stopwords
        else:
            stopwords = []

        clean_responses = []

        for response in responses:
            #self._update_users_history(response) # 更新使用者推噓文紀錄
            drop = False

            # 濾除過短與特定使用者的回應
            if response["User"] in negative_user or len(response["Content"]) < min_length:
                drop = True
            # 濾除包含停用詞的回應
            for w in stopwords:
                if w in response["Content"]:
                    drop = True
            # Drop the response containing url
            if (len(self.get_url(re.sub('\ +', '//', response["Content"]))) != 0
                or len(self.get_url(response['Content'])) != 0):
                drop = True
            # clean special markers
            for w in self.special_markers:
                response["Content"] = response["Content"].replace(w, ' ')
            response["Content"] = response["Content"].strip()
            if not drop and len(response['Content']) > 0:
                clean_responses.append(response)

        return clean_responses

    def _update_users_history(self, response):

        """
        記錄 user 的推/噓/箭頭
        """

        user = response["User"]

        if user not in self.users_info.keys():

            res = {
                "推":0,
                "噓":0,
                "箭頭":0
            }
            self.users_info[user] = res

        if response["Vote"] == "推":
            self.users_info[user]["推"] += 1
        elif response["Vote"] == "噓":
            self.users_info[user]["噓"] += 1
        else:
            self.users_info[user]["箭頭"] += 1


    def get_tag(self, title, debug=False):

        """
        回傳文章標籤與清理好的標題
        """
        if debug:
            print('Input title:', title)
        try:
            tag,title = title.split("]",1)
            tag = tag.split('[')[1]
        except:
            #print("發現無標籤標題: " + title)
            return None,title

        title = title.lstrip()
        if debug:
            print('Processed tag, title:', tag, title)
        return tag.strip(), title.strip()

    def print_titles(self):

        logging.info("正在輸出文章標題")
        with open('data/Titles.txt','w',encoding='utf-8') as op:
            for title in self.order_titles:
                op.write(title + "\n")
        logging.info("文章標題輸出完成")


if __name__ == '__main__':
    main()
