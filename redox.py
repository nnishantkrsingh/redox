""" redox - an engine to assist screenplay writing  """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import time

import threading
import multiprocessing
import urllib
from html.parser import HTMLParser
import requests
from numba import jit

import docx
from textblob import Blobber
from textblob.np_extractors import ConllExtractor
from textblob_aptagger import PerceptronTagger
from bs4 import BeautifulSoup
from GoogleScraper import scrape_with_config
TB = Blobber(pos_tagger=PerceptronTagger(), np_extractor=ConllExtractor())

class MLStripper(HTMLParser):
    """ subclassing HTMLParser """
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        """ join parsed content """
        return ''.join(self.fed)


def strip_tags(html):
    """ callinf parser """
    rparser = MLStripper()
    rparser.feed(html)
    return rparser.get_data()


def get_immediate_subdirectories(a_dir):
    """ Get only the immediate subfolders """
    return [os.path.join(PROJECTPATH, chapter)
            for chapter in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, chapter))]


def printprogress(iteration, total, prefix='', suffix='', decimals=1, pbarlength=100):
    """ progress bar """
    formatstr = "{0:." + str(decimals) + "f}"
    percent = formatstr.format(100 * (iteration / float(total)))
    filledlength = int(round(pbarlength * iteration / float(total)))
    pbar = '█' * filledlength + '-' * (pbarlength - filledlength)
    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, pbar, percent, '%', suffix))
    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()

class FetchResource(threading.Thread):
    """ Gets the content of a url """
    @jit
    def __init__(self, target, furls):
        super().__init__()
        self.target = target.strip()
        self.furls = furls
    @jit
    def run(self):
        print('\nScraping "{}"'.format(self.target.split()[-1]))
        if os.path.isdir(self.target) is False:
            os.makedirs(self.target)
        for furl in list(self.furls):
            furl = urllib.parse.unquote_plus(furl, encoding='utf-8', errors='replace')
            picname = ''.join([i if (ord(i) > 65) or (
                ord(i) == 46) else 'a' for i in furl.split('/')[-1]])
            with open(os.path.join(self.target, picname), 'wb') as picfilename:
                content = requests.get(furl).content
                picfilename.write(content)


def phrasescraper(aphrase, aprocpath):
    """ Gets images for a phrase and writes to the phrase folder """
    print("Beginning scrape for {}".format(aphrase))
    config = {'keyword': aphrase,
              'database_name' : 'redox'+aprocpath+aphrase,
              'sel_browser' : 'Phantomjs'}
    search = scrape_with_config(config)
    image_urls = []
    for serp in search.serps:
        image_urls.extend([link.link for link in serp.links])
    num_threads = 100
    phraseimages = os.path.join(aprocpath, 'images', aphrase)
    threads = [FetchResource(phraseimages, []) for i in range(num_threads)]
    while image_urls:
        for thread in threads:
            if image_urls:
                try:
                    thread.furls.append(image_urls.pop())
                except IndexError:
                    break
    threads = [thread for thread in threads if thread.furls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    print('finished phrase operations for {} at {}'.
          format(aphrase, time.strftime('%X')))


def tchunkoperations(aprocpath, sometchunks):
    """ file writing and printing """
    chapterdoc = docx.Document()
    chapterdoc.add_heading(aprocpath.split("\\")[-1], 0)
    bodytable = chapterdoc.add_table(rows=len(sometchunks), cols=1)
    progcount = 0
    printprogress(progcount, len(sometchunks), prefix='Progress:',
                  suffix='Complete\n', pbarlength=len(sometchunks))
    for tchunkno, tchunk in enumerate(sometchunks):
        tchunkcell = bodytable.cell(tchunkno, 0)
        tchunktable = tchunkcell.add_table(rows=5, cols=1)
        textcell = tchunktable.cell(0, 0)
        phrasecell = tchunktable.cell(1, 0)
        summcell = tchunktable.cell(2, 0)
        tickercell = tchunktable.cell(3, 0)
        imgcell = tchunktable.cell(4, 0)
        tchunkphrases = [[]]
        tchunkinfos = [[]]
        tickersubjectivity = 1
        for sentence in tchunk:
            for phrase in sentence.noun_phrases:
                tchunkphrases.extend(phrase)
                opener = urllib.request.build_opener()
                opener.addheaders = [('User-agent', 'Mozilla/5.0')] #wikipedia needs this
                article = urllib.request.quote(str(phrase))
                try:
                    resource = opener.open("http://en.wikipedia.org/wiki/" + article)
                    data = resource.read()
                    resource.close()
                    soup = BeautifulSoup(data, "lxml")
                    infomarkup = soup.find('div', id="bodyContent").p
                    info = TB(strip_tags(str(infomarkup)))
                    infotext = " ".join([str(infosen) for infosen in info.sentences[:2]])
                    tchunkinfos.extend(infotext[:2])
                    print("\nextracted wikipedia result for {} : {}".format(str(phrase), str(infotext)))
                except Exception:
                    pass
            if sentence.sentiment.subjectivity < tickersubjectivity:
                subticker = str(sentence)
        print("\nticker selected : {}".format(str(subticker)))
        textcell.text = " ".join([str(tch) for tch in tchunk]) + "\n" + "-"*60
        phrasecell.text = "\n".join([str(chunkinfo) for chunkinfo in tchunkinfos])
        phrasecell.add_paragraph("\n" + "-"*60)
        tickercell.text = "Ticker Suggestions :\n*2"
        tickercell.add_paragraph(str(subticker) + "\n" + "-"*60)
        imgcell.text = "_"*103
        time.sleep(0.1)
        progcount += 1
        printprogress(progcount, len(sometchunks), prefix='Progress:',
                      suffix='Complete', pbarlength=50)
    chapterdoc.save(os.path.join(aprocpath, "rawscreenplay.docx"))
    print("Wrote document at {}".format(aprocpath))

def tchunkify(aprocpath):
    """ Separate tchunks  """
    scfile = os.path.join(aprocpath, 'script.txt')
    with open(scfile, encoding='ascii', mode='r', errors='replace') as scriptfile:
        ascripttext = TB(scriptfile.read())
        scripttext = ascripttext.correct()
    tchunks = [scripttext.sentences[x:x+4] for x in range(0, len(scripttext.sentences), 4)]
    print("Corrected spellings and chunked {}\n\n".format(aprocpath.split("\\")[-1]))
    tchunkoperations(aprocpath, tchunks)

def chapterops(chapterpath):
    """ Reads the contents of a chapter and calls phrase operations"""
    if not os.path.exists(os.path.join(chapterpath, "rawscreenplay.docx")):
        tchunkify(chapterpath)
        print("Chapter {} is ready for modification !".format(chapterpath.split("\\")[-1]))
    if not os.path.exists(os.path.join(chapterpath, "finalscreenplay.docx")):
        print("Chapter {} is ready for modificatio !".format(chapterpath.split("\\")[-1]))

if __name__ == '__main__':
    PROJECTPATH = "C:\\Users\\nnikh\\Documents\\scrape"
    print("\nBeginning operations at {}\n".format(PROJECTPATH))
    CHAPTERS = get_immediate_subdirectories(PROJECTPATH)
    CHAPTERPOOL = [multiprocessing.Process(
        target=chapterops, args=(chapter,)) for chapter in CHAPTERS]
    for proc in CHAPTERPOOL:
        proc.start()
    for proc in CHAPTERPOOL:
        proc.join()
