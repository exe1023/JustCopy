'''
The python3-friendly data preprocessor for pointer-generator network
'''

from util.ptt_filter import ArticleFilter
import os
import jieba
import re
import struct
from tensorflow.core.example import example_pb2

dict_path = os.path.join(os.getenv('JIEBA_DATA'), 'dict.txt.big')
jieba.set_dictionary(dict_path)

class Interface:
    def __init__(self):
        self.filter = ArticleFilter()
        self.SENTENCE_START = '<s>'
        self.SENTENCE_END = '</s>'
        dm_single_close_quote = u'\u2019' # unicode
        dm_double_close_quote = u'\u201d'
        self.END_TOKENS = ['.', '!', '?', '...', "'", "`", '"', dm_single_close_quote, dm_double_close_quote, ")"]
    
    def prepare_news(self, content, path):
        content = self.filter.clean_content(content)
        content_cutted = ' '.join(jieba.cut(content.strip(), cut_all=False))
        content_splitted = re.sub('\ +', '\n', content_cutted).strip()
        content_splitted = re.sub('\n+', '\n', content_splitted)
        with open(path, 'w') as f:
            f.write(content_splitted + '\n')
    
    def read_text_file(self, text_file):
        lines = []
        with open(text_file, "r") as f:
            for line in f:
                if len(line.strip()) == 0:
                    continue
                lines.append(line.strip())
        return lines

    def fix_missing_period(self, line):
        """Adds a period to a line that is missing a period"""
        if "@highlight" in line: return line
        if line=="": return line
        if line[-1] in self.END_TOKENS: return line
        # print line[-1]
        return line + " ."


    def chunk_file(self, in_file, chunks_dir):
        reader = open(in_file, "rb")
        chunk = 0
        finished = False
        while not finished:
            chunk_fname = os.path.join(chunks_dir, '%s_%03d.bin' % ('test', chunk)) # new chunk
            with open(chunk_fname, 'wb') as writer:
                for _ in range(1000):
                    len_bytes = reader.read(8)
                    if not len_bytes:
                        finished = True
                        break
                    str_len = struct.unpack('q', len_bytes)[0]
                    example_str = struct.unpack('%ds' % str_len, reader.read(str_len))[0]
                    writer.write(struct.pack('q', str_len))
                    writer.write(struct.pack('%ds' % str_len, example_str))
                chunk += 1


    
    def get_art_abs(self, story_file):
        lines = self.read_text_file(story_file)

        # Lowercase everything
        lines = [line.lower() for line in lines]

        # Put periods on the ends of lines that are missing them (this is a problem in the dataset because many image captions don't end in periods; consequently they end up in the body of the article as run-on sentences)
        lines = [self.fix_missing_period(line) for line in lines]

        # Separate out article and abstract sentences
        article_lines = []
        highlights = []
        next_is_highlight = False
        for idx,line in enumerate(lines):
            if line == "":
                continue # empty line
            elif line.startswith("@highlight"):
                next_is_highlight = True
            elif next_is_highlight:
                highlights.append(line)
            else:
                article_lines.append(line)

        # Make article into a single string
        article = ' '.join(article_lines)

        # Make abstract into a signle string, putting <s> and </s> tags around the sentences
        abstract = ' '.join(["%s %s %s" % (self.SENTENCE_START, sent, self.SENTENCE_END) for sent in highlights])
        if len(highlights) == 0:
            abstract = 'test'
        #print(abstract)
        return article, abstract

    def write_to_bin(self, news_dir, out_file):
        story_fnames = os.listdir(news_dir)
        num_stories = len(story_fnames)

        with open(out_file, 'wb') as writer:
            for idx,s in enumerate(story_fnames):
                #print(s)
                # Look in the tokenized story dirs to find the .story file corresponding to this url
                if os.path.isfile(os.path.join(news_dir, s)):
                    story_file = os.path.join(news_dir, s)
                article, abstract = self.get_art_abs(story_file)

                # Write to tf.Example
                if bytes(article, 'utf-8') == 0:
                    print('error!')
                tf_example = example_pb2.Example()
                tf_example.features.feature['article'].bytes_list.value.extend([bytes(article, 'utf-8') ])
                tf_example.features.feature['abstract'].bytes_list.value.extend([bytes(abstract, 'utf-8')])
                tf_example_str = tf_example.SerializeToString()
                str_len = len(tf_example_str)
                writer.write(struct.pack('q', str_len))
                writer.write(struct.pack('%ds' % str_len, tf_example_str))

        print("Finished writing file %s\n" % out_file)
        return story_fnames