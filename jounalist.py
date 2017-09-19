from util.analyzier import Analyzier
from util.news_generator import News_Generator
from util.crawler import PttWebCrawler
from util.ptt_filter import ArticleFilter
from util.model_interface import Interface
from scripts.retriever.engine import SearchEngine
import requests
import urllib
import datetime
import os
import sys
import jieba
import schedule
import time
import subprocess
import re
import os
#from db.db import DB

dict_path = os.path.join(os.getenv("JIEBA_DATA"), "dict.txt.big") 
jieba.set_dictionary(dict_path)
#db = DB(os.getenv('DATA'))
crawler = PttWebCrawler()
analyzier = Analyzier()
Filter = ArticleFilter()
interface = Interface()
engine = SearchEngine(os.getenv('DOC'), os.getenv('TFIDF_DATA'))


def get_url(texts):
    for text in texts:
        urls = analyzier.get_url(text)
        image_urls = []
        for url in urls:
            image_url = analyzier.open_url(url)
            if image_url != None:
                return image_url


def generate_post(board, article, summary, response, title, paragraph, article_url, url, image_url):
    '''
    Generate the post for front-end website
    Args:
        board: string
        article: dict, the original article
        sumamry, response: not used, may be useful
        title, paragraph: string, the title and body of the news
        article_url: string, the link to the original article
        url: dict, the urls in article and responses.
        image_url: list, the image urls
    '''
    now = datetime.datetime.now() # The current time, may be useful

    article_encode = article_url.replace('https://www.ptt.cc/bbs/', '').replace('/', '').replace('html', '')
    filename = '{}markdown'.format(article_encode)

    # ---- Write the post head ----
    f = open(os.path.join(os.getenv('POSTS'), filename), 'w')
    f.write('---\n')
    f.write('layout: post\n')
    f.write('tags: {}\n'.format(board)) 
    f.write('title: "{}"\n'.format(title.replace('"', '')))
    f.write('date: {} +0800\n'.format(article['Date']))
    # all url in the article
    f.write('article_url: "{}"\n'.format(';'.join(url['article'])))
    # all url in the response
    f.write('response_url: "{}"\n'.format(";".join(url['response'])))
    
    preview_img = ''
    if len(image_url) > 0:
        preview_img = image_url[0]
    f.write('img: {}\n'.format(preview_img))
    
    # all image url except preview image
    if len(image_url) > 1:
        f.write('all_img: {}\n'.format(';'.join(image_url[1:])))
    
    # the response status
    response_count = article['Response_Count']
    f.write('push: {}\n'.format(response_count['push']))
    f.write('boo: {}\n'.format(response_count['boo']))
    f.write('neutral: {}\n'.format(response_count['neutral']))
    f.write('---\n\n')

    # ---- write article content ----
    
    # preview image
    if len(image_url) > 0 :
        f.write('<figure>\n')
        f.write('<img src="{}" alt="image">\n'.format(image_url[0]))
        f.write('<figcaption>\n')
        f.write('{}\n'.format(article['Title']))
        f.write('</figcaption>\n')
        f.write('</figure>\n\n')
        f.write('\n\n')

    # content
    f.write(paragraph.replace('，，', '，').replace('\n', '\n\n'))

    # link to origin article
    f.write(u'<a href = "{}">原文連結</a>\n\n'.format(article_url))




def journalist(response=False, database=True):
    '''
    Crawl and generate news
    Args:
        response: bool, whether to use the image_url in responses.
        database: bool, whether to use the image_url found in database.
    '''

    crawl_board = ['Gossiping', 'NBA', 'Baseball', 'Beauty', 'movie',
                    'Boy-Girl', 'WomenTalk', 'sex', 'KoreaStar']
    # Some boards need higher 'push' threshold
    hot_board = ['Gossiping', 'NBA']

    news_generator = News_Generator()
    
    # Whether to update the crawled board. Used to debug.
    check_exist = True

    for board in crawl_board:
        # Gossiping updates too fast
        start = -10 if board == 'Gossiping' else -5
        end = -5 if board == 'Gossiping' else -2
        
        # The push threshold
        thr = 50 if board in hot_board else 25

        cral_num = end - start + 1
        print('Crawling ', board)
        crawler.crawl(board, start=start, end=end, check_exist=check_exist)
        
        print('Writing news.....')
        for i in range(-cral_num, 0):
            articles, article_urls, urls, summarys, responses, titles, paragraphs = news_generator.find_and_generate(board=board, thr=thr, index=i)
            print('generating end')
            for j in range(len(articles)):
                if len(titles[j].strip()) == 0:
                    # If no title, don't generate
                    continue
                
                # Find the image url
                image_urls = []
                for url in urls[j]['article']:
                    image_url = analyzier.open_url(url)
                    if image_url != None:
                        image_urls.append(image_url)
                if response:
                    for url in urls[j]['response']:
                        image_url = analyzier.open_url(url)
                        if image_url != None:
                            image_urls.append(image_url)
                tag, title = Filter.get_tag(articles[j]['Title'])
                if database:
                    if len(image_urls) == 0:     
                        query = ' '.join(jieba.cut(title, cut_all=False)).strip()
                        print('search:',query)
                        search_titles, search_texts = engine.process(query, k=20)
                        print('result:', search_titles)
                        #url = db.fast_url(search_titles)
                        url = get_url(search_texts)
                        if url == None:
                            print('Database not found any url!')
                        else:
                            image_urls.append(url)
                
                # Generate post
                print('generate post')
                generate_post(board, articles[j], summarys[j], responses[j], titles[j], paragraphs[j], article_urls[j], urls[j], image_urls)
                
                # Prepare the input data of the summarization model
                #article_encode = article_urls[j].replace('https://www.ptt.cc/bbs/', '').replace('/', '').replace('html', '') 
                #interface.prepare_news(articles[j]['Content'], 'tmp/' + article_encode)

def clean_summary(sentence):
    '''
    Make summary human-friendly and remove deplicated words
    Args:
        sentence: string, the raw summary
    Return
        cleaned summary
    '''
    remove_words = ['[UNK]']
    sentence = re.sub('\ +', '', sentence)
    sentence_list = sentence.split('.')
    key_words = set(sentence_list)

    seen = set()
    cleaned_list = []
    for w in sentence_list:
        if w not in seen and w not in remove_words:
            seen.add(w)
            cleaned_list.append(w)
        
    cleaned = ''.join(cleaned_list)
    return cleaned

def add_summary(articles, summary_dir):
    '''
    Add the automatic generated summary into posts
    Args:
        articles: list, the articles we used
        summary_dir: string, where we write the summary
    '''
    summary_files = os.listdir(summary_dir)
    for summary_file in summary_files:
        summary_path = os.path.join(summary_dir, summary_file)
        with open(summary_path, 'r') as f:
            summary = f.readlines()[0]
        summary = clean_summary(summary)

        index = int(summary_file.replace('decoded', ''))
        try:
            post_name = articles[index] + 'markdown'
        except:
            continue
        post_path = os.path.join(os.getenv('POSTS'), post_name)
        with open(post_path, 'r') as f:
            content = f.read()
        with open(os.path.join('new_posts', post_name), 'w') as f:
            f.write('AutoTitle: ' + summary + '\n')
            f.write(content)

if __name__ == '__main__':
    #log_root='/home/alex/pointer-generator/log'
    #exp_name='ltn_vocab_200000'
    journalist()
    #articles = interface.write_to_bin('tmp', 'test.bin')
    #subprocess.call(['bash', 'add_model_summary.sh', log_root, exp_name])
    #add_summary(articles, os.path.join(log_root, exp_name, 'decoded'))


    #schedule.every(60).minutes.do(journalist)
    #while True:
    #    schedule.run_pending()
