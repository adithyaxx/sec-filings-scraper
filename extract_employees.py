import lxml
from urllib.request import urlopen
import sys
import os
import csv
import requests
from bs4 import BeautifulSoup, NavigableString, Comment
import re
import warnings
import urllib.error
import socket
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# Parameters
MINYEAR = 2013
MAXYEAR = 2017
FILE_10K = '10-K'
FILE_10Q = '10-Q'
CSV_FILE = 'employees.csv'

HEADERS = ['CIK', 'NAME', 'FORM', 'Filing Date', 'Filing Year', 'Filing Quarter', 'full time employees', 'extract',
           'URL']


def readfromweb(year, quarter):
    data = urlopen("https://www.sec.gov/Archives/edgar/full-index/%s/QTR%s/master.idx" % (year, quarter))
    datastring = data.read()

    return datastring


def readfromfile(year, quarter):
    with open("%s_%s.idx" % (year, quarter), "r") as f:
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


# Get the Master Index File for the every year in range
for year in range(MINYEAR, MAXYEAR):
    for qtr in range(1, 5):
        # url = 'https://www.sec.gov/Archives/edgar/full-index/%s/QTR%s/master.idx' % (year, qtr)
        # response = urlopen(url)

        if not os.path.exists("%s_%s.idx" % (year, qtr)):
            with open("%s_%s.idx" % (year, qtr), "wb") as f:
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
        for res in response:
            if string_match1 in res:
                element2 = res.split('|')
                if FILE_10Q in element2[2] or FILE_10K in element2[2]:
                    cik = element2[0]
                    company_name = element2[1]
                    form = element2[2]
                    filing_date = element2[3]
                    element4 = element2[4]

                    try:
                        # The path of the 10-K/10-Q filing
                        url3 = 'https://www.sec.gov/Archives/' + element4
                        response3 = requests.get(url3)

                        # Parse and find keywords
                        soup = BeautifulSoup(response3.text, 'html.parser')

                        print("Processing %s of %s from %s" % (form, cik, url3))

                        lines = []
                        newlines = []
                        rows_to_write = []

                        for paragraph in soup.find_all("p"):
                            split_paragraphs = re.split("\n", paragraph.text)
                            lines += split_paragraphs

                        for line in lines:
                            line = re.sub("\s+", ' ', line.strip())
                            if 50 <= len(line) <= 400:
                                # line += "."
                                newlines.append(line)

                        for i in range(0, len(newlines), 5):
                            row_to_write = [cik, company_name, form, filing_date, year, qtr]
                            keywords = []
                            line2 = newlines[i]

                            if i + 1 < len(newlines):
                                line2 += ' ' + newlines[i + 1]

                            if i + 2 < len(newlines):
                                line2 += ' ' + newlines[i + 2]

                            if i + 3 < len(newlines):
                                line2 += ' ' + newlines[i + 3]

                            if i + 4 < len(newlines):
                                line2 += ' ' + newlines[i + 4]

                            # Extract numbers near full time employee
                            if 'full-time employee' in line2.lower() or 'full time employee' in line2.lower():
                                keywords.extend([re.findall(r"(\d+)" + " full", line2.lower())])
                                keywords.extend([line2])
                            else:
                                keywords.extend([''])
                                keywords.extend([''])

                            if keywords.count('') < 2:
                                row_to_write.extend(keywords)
                                row_to_write.extend([url3])
                                if row_to_write not in rows_to_write:
                                    rows_to_write.append(row_to_write)

                        writecsv(rows_to_write)
                    except urllib.error.HTTPError as e:
                        print('HTTP Error ' + str(e.code) + ' for: ' + url3)
                        continue
                    except KeyboardInterrupt:
                        print('Script terminated manually')
                        sys.exit()
                    except socket.error as e:
                        print('Socket Error ' + str(e.errno) + ' for: ' + url3)
                    except Exception as e:
                        print(e)
                        continue
