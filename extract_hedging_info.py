import lxml
from urllib.request import urlopen
import sys
import os
import csv
from bs4 import BeautifulSoup, NavigableString, Comment
import re
import warnings
import urllib.error
import socket
import requests
import pandas as pd
from pathlib import Path
from pandas.compat import reduce
import nltk
from nltk import tokenize
import time
from tqdm import tqdm

nltk.download('punkt')

warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# Parameters
MINYEAR = 1990
MAXYEAR = 2017
FILE_10K = '10-K'
FILE_10Q = '10-Q'
CSV_FILE = 'hedging_info.csv'
IN_FILE = 'babylist.txt'

HEADERS = ['CIK', 'NAME', 'FORM', 'Filing Date', 'Filing Year', 'Filing Quarter',
           'ITEM 7A', 'P1', '% of our', 'P2', '% of projected', 'P3', 'hedg', 'P4', 'exposure to', 'P5', 'URL']


def readfromweb(year, quarter):
    data = urlopen("https://www.sec.gov/Archives/edgar/full-index/%s/QTR%s/master.idx" % (year, quarter))
    datastring = data.read()

    return datastring


def readfromfile(year, quarter):
    with open("idx/%s_%s.idx" % (year, quarter), "r") as f:
        return f.read()


def writecsv(row):
    if os.path.isfile(CSV_FILE):
        with open(CSV_FILE, 'a', encoding="utf-8") as outfile:
            writer = csv.writer(outfile)
            for data in row:
                writer.writerow(data)
    else:
        with open(CSV_FILE, 'w', encoding="utf-8") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(HEADERS)
            for data in row:
                writer.writerow(data)


def strip_html(src):
    p = BeautifulSoup(src, features="lxml")
    text = p.findAll(text=lambda text: isinstance(text, NavigableString))

    return u" ".join(text)


def remove_duplicates(duplicate):
    final_list = []
    for num in duplicate:
        if num not in final_list:
            final_list.append(num)
    return final_list


# Fetch CIK List
ciks = open(IN_FILE).read()

# Get the Master Index File for the every year in range
for year in tqdm(range(MINYEAR, MAXYEAR)):
    for qtr in range(1, 5):
        # url = 'https://www.sec.gov/Archives/edgar/full-index/%s/QTR%s/master.idx' % (year, qtr)
        # response = urlopen(url)

        try:
            if not os.path.exists("idx"):
                os.makedirs("idx")

            if not os.path.exists("idx/%s_%s.idx" % (year, qtr)):
                with open("idx/%s_%s.idx" % (year, qtr), "wb") as f:
                    f.write(readfromweb(year, qtr))

            response = readfromfile(year, qtr)
            response = response.split('\n')
            string_match1 = 'edgar/data/'
            element2 = None
            element3 = None
            element4 = None
            form = ""
            filing_date = ""
            cik = ""
            company_name = ""

            # Go through each line of the master index file, find 10K/10Q filings extract the text file path
            for i in range(0, len(response)):
                if string_match1 in response[i]:
                    element2 = response[i].split('|')
                    if FILE_10Q in element2[2] or FILE_10K in element2[2]:
                        cik = element2[0]

                        if cik in ciks:
                            company_name = element2[1]
                            form = element2[2]
                            filing_date = element2[3]
                            element4 = element2[4]

                            # The path of the 10-K/10-Q filing
                            url3 = 'https://www.sec.gov/Archives/' + element4

                            try:
                                response3 = requests.get(url3)

                                # Parse and find keywords
                                soup = BeautifulSoup(response3.text, 'html.parser')

                                percentage = i / len(response) * 100

                                # print("[%.2f%%] [%s] Processing %s from %s" % (percentage, year, cik, url3))

                                words = ['item 7a', '% of our', '% of projected', 'exposure to', 'full-time employee']

                                lines = []
                                formatted_sentences = []
                                rows_to_write = []

                                for remove in soup.find_all(["table", "tr", "td"]):
                                    remove.decompose()

                                for paragraph in soup.find_all("p"):
                                    if len(list(paragraph.children)) <= 1:
                                        formatted_paragraph = paragraph.text.replace('\n', ' ')
                                        formatted_paragraph = re.sub("\s+", ' ', formatted_paragraph)
                                        formatted_paragraph = formatted_paragraph.strip()
                                        split_sentences = tokenize.sent_tokenize(formatted_paragraph)

                                        for sen in split_sentences:
                                            if sen not in formatted_sentences and len(sen) > 50:
                                                formatted_sentences.append(sen)

                                for index in range(0, len(formatted_sentences), 5):
                                    row_to_write = [cik, company_name, form, filing_date, year, qtr]
                                    keywords = []
                                    line2 = formatted_sentences[index]

                                    if index + 1 < len(formatted_sentences):
                                        line2 += ' ' + formatted_sentences[index + 1]

                                    if index + 2 < len(formatted_sentences):
                                        line2 += ' ' + formatted_sentences[index + 2]

                                    if index + 3 < len(formatted_sentences):
                                        line2 += ' ' + formatted_sentences[index + 3]

                                    if index + 4 < len(formatted_sentences):
                                        line2 += ' ' + formatted_sentences[index + 4]

                                    num1 = None
                                    num2 = None

                                    # Extract numbers near Item 7A
                                    if words[0] in line2.lower():
                                        keywords.extend([re.findall(r"(\d+\.\d+)", line2.lower()) +
                                                         re.findall(r"(\d+ )", line2.lower())])
                                        keywords.extend([line2])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    # Extract numbers near '% of our'
                                    if words[1] in line2.lower() and 'hedg' in line2.lower():
                                        # Find all numbers before keyword
                                        num1 = re.findall(r"(\d+\.\d+)" + words[1], line2.lower()) + \
                                               re.findall(r"(\d+\.\d+ )" + words[1], line2.lower()) + \
                                               re.findall(r"(\d+)" + words[1], line2.lower()) + \
                                               re.findall(r"(\d+ )" + words[1], line2.lower())

                                        if num1:
                                            keywords.extend([num1])
                                            keywords.extend([line2])
                                        else:
                                            keywords.extend([''])
                                            keywords.extend([''])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    # Extract numbers near '% of projected'
                                    if words[2] in line2.lower() and 'hedg' in line2.lower():
                                        # Find all numbers before keyword
                                        num2 = re.findall(r"(\d+\.\d+)" + words[2], line2.lower()) + \
                                               re.findall(r"(\d+\.\d+ )" + words[2], line2.lower()) + \
                                               re.findall(r"(\d+)" + words[2], line2.lower()) + \
                                               re.findall(r"(\d+ )" + words[2], line2.lower())

                                        if num2:
                                            keywords.extend([num2])
                                            keywords.extend([line2])
                                        else:
                                            keywords.extend([''])
                                            keywords.extend([''])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    # Extract numbers near hedg if the previous 2 search criteria get no hits
                                    if 'hedg' in line2.lower() and num1 is None and num2 is None:
                                        num3 = re.findall(r"(\d+\.\d+)", re.sub(r',', '', line2.lower())) + \
                                               re.findall(r"(\d+ )", re.sub(r',', '', line2.lower()))

                                        if num3:
                                            keywords.extend([num3])
                                            keywords.extend([line2])
                                        else:
                                            keywords.extend([''])
                                            keywords.extend([''])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    # Extract numbers near 'exposure to'
                                    if words[3] in line2.lower():
                                        num4 = re.findall(r"\$(\d+\.\d+)", re.sub(r',', '', line2.lower())) +\
                                               re.findall(r"\$(\d+ )", re.sub(r',', '', line2.lower()))

                                        if num4:
                                            keywords.extend([num4])
                                            keywords.extend([line2])
                                        else:
                                            keywords.extend([''])
                                            keywords.extend([''])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    if keywords.count('') < 10:
                                        row_to_write.extend(keywords)
                                        row_to_write.extend([url3])
                                        if row_to_write not in rows_to_write:
                                            rows_to_write.append(row_to_write)

                                writecsv(rows_to_write)
                            except urllib.error.HTTPError as e:
                                # print('HTTP Error ' + str(e.code) + ' for: ' + url3)
                                continue
                            except KeyboardInterrupt:
                                # print('Script terminated manually')
                                sys.exit()
                            except socket.error as e:
                                # print('HTTP Error ' + str(e.errno) + ' for: ' + url3)
                                continue
                            except Exception as e:
                                # print(e)
                                continue
        except urllib.error.HTTPError as e:
            # print('HTTP Error ' + str(e.code) + ' for: ' + str(year) + 'Q' + str(qtr))
            continue
