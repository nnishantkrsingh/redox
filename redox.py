""" redox - an engine to assist screenplay writing  """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import time
import threading
import urllib
import traceback
from concurrent.futures import ProcessPoolExecutor
import requests
from textblob import Blobber
from textblob.np_extractors import ConllExtractor
from textblob_aptagger import PerceptronTagger
from GoogleScraper import scrape_with_config
import docx

TB = Blobber(pos_tagger=PerceptronTagger(), np_extractor=ConllExtractor())

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
    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, pbar, percent, '%', suffix)),
    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()

def uprint(*objects, sep=' ', end='\n', file=sys.stdout):
    """This is just a print wrapper"""
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        fup = lambda obj: str(obj).encode(enc, errors='replace').decode(enc)
        print(*map(fup, objects), sep=sep, end=end, file=file)

class FetchResource(threading.Thread):
    """ Gets the content of a url """
    def __init__(self, target, furls):
        super().__init__()
        self.target = target.strip()
        self.furls = furls
    def run(self):
        uprint('\nScraping "{}"'.format(self.target.split()[-1]))
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
    uprint("Beginning scrape for {}".format(aphrase))
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
    uprint('finished phrase operations for {} at {}'.format(aphrase, time.strftime('%X')))

def chunkoperations(aprocpath, somechunks):
    """ file writing and printing """
    uprint("Creating docx for {}".format(aprocpath.split("\\")[-1]))
    chapterdoc = docx.Document()
    chapterdoc.add_heading(aprocpath.split("\\")[-1], 0)
    bodytable = chapterdoc.add_table(rows=len(somechunks), cols=1)
    progcount = 0
    uprint("Creating progress bar")
    printprogress(progcount, len(somechunks), prefix='Progress:', suffix='Complete', pbarlength=50)
    for chunkno, chunk in enumerate(somechunks):
        chunkcell = bodytable.cell(chunkno, 0)
        chunktable = chunkcell.add_table(rows=5, cols=1)
        textcell = chunktable.cell(0, 0)
        phrasecell = chunktable.cell(1, 0)
        summcell = chunktable.cell(2, 0)
        tickercell = chunktable.cell(3, 0)
        imgcell = chunktable.cell(4, 0)
        chunkphrases = []
        tickersubjectivity = 1
        for sentence in chunk:
            for phrase in sentence.noun_phrases:
                chunkphrases.extend(phrase)
            if sentence.sentiment.subjectivity < tickersubjectivity:
                subticker = sentence
        textcell.text = " ".join(map(str, chunk)) + "\n" + "-"*60
        phrasecell.text = " ".join(map(str, chunkphrases)) + "\n" + "-"*60
        tickercell.text = "Ticker Suggestions :" + "\n"*2 + str(subticker) + "\n" + "-"*60
        imgcell.text = "_"*103
        time.sleep(0.1)
        progcount += 1
        printprogress(progcount, len(somechunks), prefix='Progress:',
                      suffix='Complete', pbarlength=50)
    chapterdoc.save(os.path.join(aprocpath, "rawscreenplay.docx"))

def chunkify(aprocpath):
    """ Separate chunks  """
    uprint("Spellchecking and chunking {}\n\n".format(aprocpath.split("\\")[-1]))
    scfile = os.path.join(aprocpath, 'script.txt')
    with open(scfile, encoding='ascii', mode='r', errors='replace') as scriptfile:
        ascripttext = TB(scriptfile.read())
        scripttext = ascripttext.correct()
    uprint("\nRead script for {}\n".format(aprocpath.split("\\")[-1]))
    chunks = [scripttext.sentences[x:x+4] for x in range(0, len(scripttext.sentences), 4)]
    uprint("\nCreated chunks for {}\n".format(aprocpath.split("\\")[-1]))
    chunkoperations(aprocpath, chunks)

def chapterops(chapterpath):
    """ Reads the contents of a chapter and calls phrase operations"""
    if not os.path.exists(os.path.join(chapterpath, "rawscreenplay.docx")):
        uprint("Raw screenplay found for {}".format(chapterpath.split("\\")[-1]))
        chunkify(chapterpath)
        uprint("Chapter {} is ready for modification !".format(chapterpath.split("\\")[-1]))
    if not os.path.exists(os.path.join(chapterpath, "finalscreenplay.docx")):
        uprint("Chapter {} is ready for modificatio !".format(chapterpath.split("\\")[-1]))

if __name__ == '__main__':
    PROJECTPATH = "C:\\Users\\nnikh\\Documents\\scrape"
    uprint("\nBeginning Scrape for {}\n".format(PROJECTPATH))
    CHAPTERS = get_immediate_subdirectories(PROJECTPATH)
    with ProcessPoolExecutor() as executor:
        for chapterop, chapter in zip(CHAPTERS, executor.map(chapterops, CHAPTERS)):
            print("{} is ready ".format(chapter))
