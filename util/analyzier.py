import os
import sys
import json
import random
import re
import math
import urllib
import requests
import copy
import metadata_parser
from util.textrank4zh import TextRank4Keyword, TextRank4Sentence
from util.ptt_filter import ArticleFilter

dict_path = os.path.join(os.getenv("JIEBA_DATA"), "dict.txt.big") 
stopword_path = os.path.join(os.getenv("DATA"), "stopwords/chinese_sw.txt" )


class Analyzier:
    ''' Analyze the ptt article '''
    def __init__(self):
        '''
        tr4s: extract keysentences
        tr4w: extract keywords
        filter: clean the text and use some magic regex
        '''
        self.tr4s = TextRank4Sentence(stop_words_file = stopword_path)
        self.tr4w = TextRank4Keyword(stop_words_file= stopword_path)
        self.filter = ArticleFilter()

    def get_url(self, content):
        ''' 
        get the url from content
        Args: 
            url: string
        Return: 
            list of string
        '''
        return self.filter.get_url(content)

    def get_content_len(self, content):
        '''
        get the length of content
        Args: 
            content: string
        Return: 
            integer
        '''
        clean_content = self.filter.clean_content(content=content)
        return len(clean_content.split('\n'))
    
    def get_response_num(self, responses):
        '''
        get the number of useful responses
        Args: 
            responses: list of dict
        Return: 
            integer
        '''
        clean_responses = self.filter.clean_responses(responses, self.filter.stopwords)
        print('Response: {}, Clean response: {}'.format(len(responses), len(clean_responses)))
        return len(clean_responses)

    def get_response_url(self, responses):
        '''
        get all url from the responses
        Args: 
            responses: list of dict
        Return: 
            list of string
        '''
        urls = []
        for response in responses:
            content = re.sub('\ +', '//', response['Content'])
            urls += self.filter.get_url(response['Content'])
            urls += self.filter.get_url(content)
        return list(set(urls))

    def check_article(self, content):
        '''
        check whether the article is 'Give P Coin' article
        Args: 
            content: string
        Return: 
            bool
        '''
        pattern = '[0-9]+?P'
        reward = re.findall(pattern, content)
        if len(reward) > 0:
            return True
        else:
            return False

    def open_url(self, url):
        '''
        Try to get the image url from the input url
        If the input url is not a image and open graph protocal
        gives nothing, it returns 'None'
        Args: 
            url: string
        Return: 
            string or None
        '''
        def get_type(url):
            print(url)
            try:
                with urllib.request.urlopen(url) as response:
                    mime_type = response.info().get_content_type()
                print(mime_type)
                return mime_type.split('/')
            except:
                return [None, None]
        if get_type(url)[0] == 'image':
            return url
        else:
            print('try og')
            try:
                page = metadata_parser.MetadataParser(url=url)
                image_link = page.get_metadata_link('image')
                if image_link != None:
                    #image_url.append(image_link)
                    return image_link
            except:
                return None
    
    def find_summary(self, content, summary_num = 5, debug=True):
        '''
        generate the summary from input content
        Args: 
            content: string
            summary_num: integer, how many summary you want
            debug: bool, whether to print the result
        Return:
            list of string
        '''
        clean_content = self.filter.clean_content(content=content)
        
        # at most extract (content / 5) sentences from content
        max_num = int(len(clean_content.split('\n'))/5) 
        num = max_num if max_num > summary_num * 2 else summary_num * 2
        if len(clean_content) < 150: # if the article is short enough
            num = 1e6
        if num > 20: # if the article is too long
            num = 20

        key_sentences = self.extract_key_sentences(clean_content, sort_by_index=True, num = num)
        key_sentences = [x[2] for x in key_sentences]
        if debug:
            print('Original content:', content)
            print('Cleaned content:', clean_content)
            print('Length of cleaned content:', len(clean_content))
            print('Key sentences:', key_sentences)
            print('Num of key sentences', len(key_sentences))
        
        '''
        Divide the keysentences into $summary_num part
        '''
        summarys = []
        summary_len = [1 for _ in range(summary_num)] # each part deserve 1 sentence
        rest = len(key_sentences) - summary_num # num of remain sentences
        if rest > summary_num:
            # equally distribute the key sentences to all part
            factor = int(rest/summary_num)
            rest = rest - (factor * summary_num)
            summary_len = [x + factor for x in summary_len]
        rest_count = 0
        for i in range(len(summary_len)):
            if rest > 0:
                # assign the remain sentences if we have
                summary_len[i] += 1
                rest -= 1
            summarys.append('，'.join(key_sentences[rest_count:rest_count + summary_len[i]]))
            rest_count += summary_len[i]

        return summarys
    
    def find_useful_response(self, responses, num = 5):
        clean_responses = self.filter.clean_responses(responses, self.filter.stopwords)
        if len(clean_responses) != 0:
            responses = clean_responses

        ''' 
        preserve the original responses
        merge the all responses into one article
        '''
        response_dict = {}
        all_response = ''
        for response in responses:
            all_response += response['Content'].replace(' ', '') + '\n'
            response_dict[response['Content'].replace(' ','').strip()] = response
        
        # run text rank
        key_responses = self.extract_key_sentences(all_response, sort_by_index=False, num=num)
        important_responses = []
        
        # restore the responses
        for r in key_responses:
            if r[2].strip() in response_dict.keys():
                response = response_dict[r[2].strip()]
                author, content = response['User'], response['Content']
                ipdatetime, vote = response['Ipdatetime'], response['Vote']
            else:
                author, content = 'unk', r[2]
                ipdatetime, vote = 'unk', 'unk'
            content = re.sub('\ +', '，', content)
            important_responses.append({'author':author, 'content':content, 'vote':vote, 'ipdatetime':ipdatetime})
        return important_responses
    
    def extract_keywords(self, content):
        '''
        extract the keywords from content
        Args:
            content: string
        Return:
            key_words: list of string
        '''
        clean_content = self.filter.clean_content(content=content)
        self.tr4w.analyze(text=clean_content, lower=True, window=2)
        key_words = []
        for item in self.tr4w.get_keywords(20, word_min_len=1):
            #print(item.word, item.weight)
            key_words.append(item.word)
        return key_words
        
    def extract_key_sentences(self, content, sort_by_index=False, num = 5):
        '''
        extract keysentences from content
        Args:
            content: string
            sort_by_index: bool, whether sort the output by line index
            num: integer, how many sentences we want
        Return:
            list of information of key_sentences
        '''
        self.tr4s.analyze(text=content, lower=True, source = 'all_filters')
        key_sentences = []
        for item in self.tr4s.get_key_sentences(num=num, sentence_min_len=1):
            key_sentences.append([item.index, item.weight, item.sentence])
            #print(item.index, item.weight, item.sentence) 
        #print('=====')
        def index(x):
            return x[0]
        def weight(x):
            return x[1]

        return sorted(key_sentences, key=index) if sort_by_index else sorted(key_sentences, key=weight)

if __name__ == '__main__':
    news_generator = News_Generator()
    print(news_generator.find_and_generate())
    #print(news_generator.get_template(t_type='ask'))