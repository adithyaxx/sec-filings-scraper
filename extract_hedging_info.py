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
import datetime

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

HEADERS = ['CIK', 'NAME', 'FORM', 'Filing Date', 'Filing Year', 'Filing Quarter', 'Conformed Period', 'Standard Industrial Classification',
           'State of Incorporation', 'City', 'State', '% + hedg', 'P1', 'hedg', 'P2', 'URL']


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
            conformed_period = ""
            standard_industrial = ""
            state_of_incorporation = ""
            city = ""
            state = ""

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

                                lines = []
                                formatted_sentences = []
                                rows_to_write = []

                                sptext = str(soup.get_text)
                                for paragraph in sptext.split("\n"):
                                    paragraph = re.sub('\s+', ' ', paragraph)

                                    if 'CONFORMED PERIOD OF REPORT:' in paragraph:
                                        split_by_colon = paragraph.split(':')
                                        fetched_date = split_by_colon[1].strip()
                                        conformed_period = '%s-%s-%s' % (fetched_date[0:4], fetched_date[4:6], fetched_date[6:])

                                    if "STANDARD INDUSTRIAL CLASSIFICATION:" in paragraph:
                                        split_by_colon = paragraph.split(':')
                                        standard_industrial = split_by_colon[1].strip()

                                    if 'STATE OF INCORPORATION:' in paragraph:
                                        split_by_colon = paragraph.split(':')
                                        state_of_incorporation = split_by_colon[1].strip()

                                    if "CITY:" in paragraph:
                                        split_by_colon = paragraph.split(':')
                                        city = split_by_colon[1].strip()

                                    if 'STATE:' in paragraph:
                                        split_by_colon = paragraph.split(':')
                                        state = split_by_colon[1].strip()

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
                                    row_to_write = [cik, company_name, form, filing_date, year, qtr, conformed_period, standard_industrial, state_of_incorporation, city, state]
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

                                    # Extract numbers near '% of projected'
                                    if '%' in line2.lower() and 'hedg' in line2.lower():
                                        # Find all numbers before keyword
                                        num1 = re.findall(r"(\d+\.\d+)" + '%', line2.lower()) + \
                                               re.findall(r"(\d+\.\d+ )" + '%', line2.lower()) + \
                                               re.findall(r"(\d+)" + '%', line2.lower()) + \
                                               re.findall(r"(\d+ )" + '%', line2.lower())

                                        if num1:
                                            keywords.extend([num1])
                                            keywords.extend([line2])
                                        else:
                                            keywords.extend([''])
                                            keywords.extend([''])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    # Extract numbers near hedg if the previous 2 search criteria get no hits
                                    if 'hedg' in line2.lower() and num1 is None:
                                        keywords.extend(['NA'])
                                        keywords.extend([line2])
                                    else:
                                        keywords.extend([''])
                                        keywords.extend([''])

                                    if keywords.count('') < 4:
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
