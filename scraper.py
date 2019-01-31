from urllib.request import urlopen
import os
import csv
from bs4 import BeautifulSoup, NavigableString
import re

# Parameters
MINYEAR = 2014
MAXYEAR = 2015
FILE_10K = '10-K'
FILE_10Q = '10-Q'
CSV_FILE = 'out.csv'
HEADERS = ['CIK', 'NAME', 'FORM', 'Filing Date', 'Filing Year', 'Filing Quarter', '% of our', 'P1',
           'ITEM 7A', 'P2', 'Hedg', 'P3', '% of projected', 'P4', 'Employee', 'P5', 'URL']


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
    p = BeautifulSoup(src)
    text = p.findAll(text=lambda text: isinstance(text, NavigableString))

    return u" ".join(text)


# Get the Master Index File for the every year in range
for year in range(MINYEAR, MAXYEAR):
    for qtr in range(1, 5):
        url = 'https://www.sec.gov/Archives/edgar/full-index/%s/QTR%s/master.idx' % (year, qtr)
        response = urlopen(url)
        string_match1 = 'edgar/data/'
        element2 = None
        element3 = None
        element4 = None
        form = ""
        filing_date = ""
        cik = ""
        company_name = ""

        # Go through each line of the master index file, find 10K/10Q filings extract the text file path
        for line in response:
            if string_match1 in line.decode():
                print(line)
                element2 = line.decode().split('|')
                print(element2)
                if FILE_10Q in element2[2] or FILE_10K in element2[2]:
                    cik = element2[0]
                    company_name = element2[1]
                    form = element2[2]
                    filing_date = element2[3]
                    element4 = element2[4]
                    # The path of the 10-K/10-Q filing
                    url3 = 'https://www.sec.gov/Archives/' + element4
                    print("Processing %s of %s from %s" % (form, cik, url3))
                    response3 = urlopen(url3)
                    #response3 = strip_html(response3)
                    soup = BeautifulSoup(response3)
                    text = soup.get_text()
                    words = ['% of our', 'ITEM 7A', 'hedg', '% of projected', 'employee']

                    rows_to_write = []
                    lines = re.split(r'([.\n])', text)
                    for line2 in lines:
                        line2 = strip_html(line2)
                        row_to_write = [cik, company_name, form, filing_date, year, qtr]
                        keywords = []
                        for word in words:
                            if word in line2:
                                keywords.extend([word])
                                keywords.extend([line2])
                            else:
                                keywords.extend([''])
                                keywords.extend([''])

                        if keywords.count('') < 9:
                            row_to_write.extend(keywords)
                            row_to_write.extend([url3])
                            rows_to_write.append(row_to_write)

                    writecsv(rows_to_write)
