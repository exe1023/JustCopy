import os
import json
import re
import random
from util.ptt_filter import ArticleFilter
from util.analyzier import Analyzier

class Template:
    ''' Handle the template '''
    def __init__(self):
        self.template_path = os.getenv('TEMPLATE')
        self.load_template()
        self.tag_mapping = {'問卦' : 'ask', '爆卦' : 'explode', '回覆': 'reply'}
        self.date_pattern = '\{date\}'
        self.time_pattern = '\{time\}'
        self.title_pattern = '\{title\}' 
        self.author_pattern = '\{author\}' 
        self.board_pattern = '\{board\}'
        self.summary_pattern = '\{summary_[0-9]*?\}' # may have sumamry_1, sumamry_2...
        self.comment_pattern = '\{comment_[0-9]*?\}' # may have comment_1, comment_2
        self.comment_special_pattern = '\{comment_special_[0-9]*?\}' # may have comment_special_1 .....
        self.comment_by_pattern = ('\{comment_by_[0-9]*?\}', 'comment_summary') # may have comment_by_1, comment_by_2...
    
    def load_template(self):
        '''
        load all templates
        '''
        types = [t for t in os.listdir(self.template_path) if not t.startswith('.')]
        self.all_templates = {}
        for t in types:
            self.all_templates[t] = []
            template_path = os.path.join(self.template_path, t)
            template_names = [name for name in os.listdir(template_path) if not name.startswith('.')]
            for template_name in template_names:
                with open(os.path.join(template_path, template_name), 'r') as f:
                    self.all_templates[t].append(json.load(f))

    def get_template(self, t_type, max_summary, max_response):
        '''
        get the proper template
        Args:
            t_type: string, tag of the article
            max_sumamry: integer, the maximum summary num
            max_responses: integer, the maximum responses num
        Return:
            template class
        '''
        if t_type not in self.tag_mapping.keys():
            t_type = 'wildcard'
        else:
            t_type = self.tag_mapping[t_type]
        
        candidates = []
        for template in self.all_templates[t_type]:
            if template['summary_num'] <= max_summary and template['comment_num'] <= max_response:
                candidates.append(template)
        
        self.history = {} # remember the used tag
        if len(candidates) > 0:
            chosen = random.choice(candidates)
        else:
            chosen = None
        print(chosen)
        return chosen

    def process_template(self, sentence, date, time, title, author, board, summary, responses):
        '''
        fill the slots in sentence
        Args:
            sentence: string, the template sentence
            date, time, title, author, board, summay, responses: string
        Return:
            filled sentence
        '''
        date_match = re.findall(self.date_pattern, sentence)
        time_match = re.findall(self.time_pattern, sentence)
        title_match = re.findall(self.title_pattern, sentence)
        author_match = re.findall(self.author_pattern, sentence)
        board_match = re.findall(self.board_pattern, sentence)
        summary_match = re.findall(self.summary_pattern, sentence)
        comment_match = re.findall(self.comment_pattern, sentence)
        comment_special_match = re.findall(self.comment_special_pattern, sentence)
        comment_by_match = re.findall(self.comment_by_pattern[0], sentence)
        if len(date_match) > 0:
            sentence = sentence.replace(date_match[0], date) 
        if len(time_match) > 0:
            sentence = sentence.replace(time_match[0], time)
        if len(title_match) > 0:
            sentence = sentence.replace(title_match[0], title)
        if len(author_match) > 0:
            sentence = sentence.replace(author_match[0], author)
        if len(board_match) > 0:
            sentence = sentence.replace(board_match[0], board)
        if len(summary_match) > 0:
            for m in summary_match:
                if m not in self.history.keys():
                    self.history[m] = summary.pop(0)
                sentence = sentence.replace(m, self.history[m])
        if len(comment_match) > 0:
            for m in comment_match:
                if m not in self.history.keys():
                    self.history[m] = responses.pop(0)['content']
                sentence = sentence.replace(m, self.history[m])
        if len(comment_special_match) > 0:
            for m in comment_special_match:
                if m not in self.history.keys():
                    self.history[m] = responses.pop()['content']
                sentence = sentence.replace(m, self.history[m])
        if len(comment_by_match) > 0:
            for m in comment_by_match:
                if m not in self.history.keys():
                    response = responses.pop()
                    self.history[m] = (response['author'], response['content'])
                sentence = sentence.replace(m, self.history[m][0])
                sentence = sentence.replace(m.replace('comment_by', self.comment_by_pattern[1]), self.history[m][1])
        return sentence
            
        
    def fill_template(self, template, date, time, title, author, board, summary, responses):
        '''
        Fill the template
        Args:
            template: dict, the template
            date, time, title, author, board: string, the necessary information
            sumamry, responses: list, summary of article and responses
        Return:
            news_title: string, title of the generated news
            news_paragraph: string, paragraphhs of the generated news
        '''
        template_title, template_paragraphs = template['title'], template['paragraphs']
        news_title = self.process_template(template_title, date, time, title, author, board, summary, responses)
        news_paragraph = ''
        for template_paragraph in template_paragraphs:
            news_paragraph += self.process_template(template_paragraph, date, time, title, author, board, summary, responses)
            news_paragraph += '\n'
        print(news_title, news_paragraph)
        return news_title, news_paragraph


class News_Generator:
    ''' Generate the news '''
    def __init__(self):
        '''
        filter: clean the text and use some magic regex
        remove_tag: skip these tags when generating news
        data_path: path of data directory
        analyzier: analyze the crawled article
        template: handle the taiwan journalist template
        '''
        self.filter = ArticleFilter()
        self.remove_tag = ['公告', '協尋', '新聞']
        self.data_path = os.path.join(os.getenv("DATA"), "raw" ) 
        self.analyzier = Analyzier()
        self.template = Template()

    def find_and_generate(self, board='Gossiping', thr=10, index=-1):
        '''
        Find the crawled ptt page and generate news
        Args:
            board: string, specify the ptt board
            thr: integer, the threshold of 'push'
            index: integer, specify the page
        Return:
            used_article: list, articles used to generate news
            article_urls: list, the urls linked to original article
            urls: list, the urls which appears in the article
            sumamry, response: list, the summary and key responses of articles
            titles: list, the title of news
            paragraphs: list, the paragraphs of news
        '''
        print('Generate news from', board)
        used_article, article_urls, urls, titles, paragraphs = [], [], [], [], []
        summarys, responses = [], []

        articles = self.get_articles(board, index)
        for article in articles:
            try:
                push_num = article['Response_Count']['push']
            except:
                push_num = 0
            if push_num > thr:
                article_url, url, summary, response, title, paragraph = self.generate_news(article)
                if title != None and paragraph != None:
                    used_article.append(article)
                    titles.append(title)
                    paragraphs.append(paragraph)
                    urls.append(url)
                    article_urls.append(article_url)
                    summarys.append(summary)
                    responses.append(response)
        return used_article, article_urls, urls, summarys, responses, titles, paragraphs

    def time_mapper(self, time):
        '''
        Map the time into modern Mandarin
        Args:
            time: string
        Return:
            the Mandarin form of time
        '''
        splited_time = list(map(int, time.split(':')))
        return '{}點{}分{}秒'.format(splited_time[0],splited_time[1],splited_time[2])

    def date_mapper(self, date):
        '''
        Map the date into modern Mandarin
        Args:
            date: string
        Return:
            the Mandarin form of date
        '''
        splited_date = date.split()
        month = {'Jan':'1', 'Feb':'2','Mar':'3',
                'Apr':'4', 'May':'5', 'Jun':'6',
                'Jul':'7', 'Aug':'8', 'Sep':'9',
                'Oct':'10', 'Nov':'11', 'Dec':'12'}
        return '{}年{}月{}日'.format(splited_date[3],
                                    month[splited_date[1]],
                                    splited_date[2])


    def generate_news(self, article):
        '''
        Generate the news from article
        Args:
            article: dict, the crawled article
        Return:
            article_url: string, the url linked to article
            url: string, the urls which appears in the article
            all_sumamry, all_response: list, the summary and key responses of articles
            title: string, the title of news
            paragraph: string, the paragraphs of news
        '''
        # Filter out some special article
        if article['Title'].startswith('Fw') or self.analyzier.check_article(article['Content']):
            return None, None, None, None, None, None

        # Split the tag and title
        tag, title = self.filter.get_tag(article['Title'])
        if tag in self.remove_tag:
            print('Tag {} is ignored!'.format(tag))
            return None, None, None, None, None, None
        if article['Title'].startswith('Re'):
            tag = '回覆'

        # Get the template
        max_summary = self.analyzier.get_content_len(article['Content'])
        max_response = self.analyzier.get_response_num(article['Responses'])
        print('max sumamry:{}, max response:{}'.format(max_summary, max_response))
        template = self.template.get_template(tag, max_summary, max_response)
        if template == None:
            print('No template!')
            return None, None, None, None, None, None
        
        # Clean author id
        author = article['Author']
        author = re.sub('\(.*?\)', '', author).strip()

        # Deal with urls
        board = article['Board']
        article_url = 'https://www.ptt.cc/bbs/' + article['Board'] + '/' + article['Article_id'] + '.html'
        url = {'article': self.analyzier.get_url(article['Content']), 'response':self.analyzier.get_response_url(article['Responses'])}
        print('url', url)

        # Extract summary and response
        summarys = self.analyzier.find_summary(article['Content'], template['summary_num'])
        responses = self.analyzier.find_useful_response(article['Responses'], template['comment_num'])
        print(responses)

        # Deal with the article date
        all_date = article['Date'].split()
        if len(all_date) < 5:
            # When the crawler failed, give special value
            time = '11:26:26'
            date = 'Thu Jul 20 2017'
        else:
            time = all_date.pop(3)
            date = ' '.join(all_date)
        time, date = self.time_mapper(time), self.date_mapper(date)
        
        # Fill the template
        title, paragraph = self.template.fill_template(template, date, time, title, author, board, summarys, responses)

        # Maybe we want the pure summary and key responses
        clean_content = self.analyzier.filter.clean_content(content=article['Content'])
        key_summary = self.analyzier.extract_key_sentences(clean_content, sort_by_index=True, num = 20)
        all_summary = [s[2] for s in key_summary]
        all_response = self.analyzier.find_useful_response(article['Responses'], 20)

        return article_url, url, all_summary, all_response, title, paragraph
    
    def get_articles(self, board, index=1):
        '''
        Get the crawled page by the modified time
        Args:
            board: string, specify the board
            index: get index(st) page from the directory
        Return:
            articles
        '''
        def get_pagenum(filename):
            return int(re.findall(r'\d+', filename)[0])
        def get_modified(filename):
            return os.path.getctime(filename)
        path = os.path.join(self.data_path, board)
        filenames = [os.path.join(path, name) for name in os.listdir(path) if not name.startswith(".")]
        filenames = sorted(filenames, key=get_modified)
        file = filenames[index]
        print('check the existence of ', file)
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                articles = json.load(f)
            return articles
        else:
            print('No such file!')
            return []
