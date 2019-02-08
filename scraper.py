import lxml
from urllib.request import urlopen
import os
import csv
import requests
from bs4 import BeautifulSoup, NavigableString, Comment
import re
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

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
    p = BeautifulSoup(src, features="lxml")
    text = p.findAll(text=lambda text: isinstance(text, NavigableString))

    return u" ".join(text)


def is_line_break(e):
    """Is e likely to function as a line break when document is rendered?
    we are including 'HTML block-level elements' here. Note <p> ('paragraph')
    and other tags may not necessarily force the appearance of a 'line break',
    on the page if they are enclosed inside other elements, notably a
    table cell
    """

    is_block_tag = e.name != None and e.name in ['p', 'div', 'br', 'hr', 'tr',
                                                 'table', 'form', 'h1', 'h2',
                                                 'h3', 'h4', 'h5', 'h6']
    # handle block tags inside tables: if the apparent block formatting is
    # enclosed in a table cell <td> tags, and if there are no other block
    # elements within the <td> cell (it's a singleton, then it will not
    # necessarily appear on a new line so we don't treat it as a line break
    if is_block_tag and e.parent.name == 'td':
        if len(e.parent.findChildren(name=e.name)) == 1:
            is_block_tag = False
    # inspect the style attribute of element e (if any) to see if it has
    # block style, which will appear as a line break in the document
    if hasattr(e, 'attrs') and 'style' in e.attrs:
        is_block_style = re.search('margin-(top|bottom)', e['style'])
    else:
        is_block_style = False
    return is_block_tag or is_block_style


def get_text(soup):
    paragraph_string = ''
    document_string = ''
    all_paras = []
    ec = soup.find()
    is_in_a_paragraph = True
    while not (ec is None):
        if is_line_break(ec) or ec.next_element is None:
            # end of paragraph tag (does not itself contain
            # Navigable String): insert double line-break for readability
            if is_in_a_paragraph:
                is_in_a_paragraph = False
                all_paras.append(paragraph_string)
                document_string = document_string + '\n\n' + paragraph_string
        else:
            # continuation of the current paragraph
            if isinstance(ec, NavigableString) and not \
                    isinstance(ec, Comment):
                # # remove redundant line breaks and other whitespace at the
                # # ends, and in the middle, of the string
                # ecs = re.sub(r'\s+', ' ', ec.string.strip())
                ecs = re.sub(r'\s+', ' ', ec.string)
                if len(ecs) > 0:
                    if not is_in_a_paragraph:
                        # set up for the start of a new paragraph
                        is_in_a_paragraph = True
                        paragraph_string = ''
                    # paragraph_string = paragraph_string + ' ' + ecs
                    paragraph_string = paragraph_string + ecs
        ec = ec.next_element
    # clean up multiple line-breaks
    # document_string = re.sub('\n\s+\n', '\n\n', document_string)
    # document_string = re.sub('\n{3,}', '\n\n', document_string)
    return document_string


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
        for res in response:
            if string_match1 in res.decode():
                element2 = res.decode().split('|')
                if FILE_10Q in element2[2] or FILE_10K in element2[2]:
                    cik = element2[0]
                    company_name = element2[1]
                    form = element2[2]
                    filing_date = element2[3]
                    element4 = element2[4]
                    # The path of the 10-K/10-Q filing
                    url3 = 'https://www.sec.gov/Archives/' + element4
                    print("Processing %s of %s from %s" % (form, cik, url3))
                    response3 = requests.get(url3)
                    soup = BeautifulSoup(response3.text, 'html.parser')
                    for table in soup.find_all("table"):
                        table.decompose()
                    for headers in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a', 'U', 'A']):
                        headers.decompose()
                    # text = get_text(soup)
                    text = strip_html(soup.getText())
                    words = ['% of our', 'item 7a', 'hedg', '% of projected', 'full-time employee']

                    rows_to_write = []
                    lines = re.split("\\. |\n", text)
                    newlines = []

                    for line in lines:
                        line = re.sub("\s+", ' ', line.strip())
                        if 50 <= len(line) <= 400:
                            line += "."
                            newlines.append(line)

                    '''
                    text_file = open("out.txt", "w")

                    for tmpln in newlines:
                        tmpln = re.sub("\s+", ' ', tmpln.strip())

                        if (tmpln != ' ') and (tmpln != '') and ('us-gaap' not in tmpln) and (not tmpln.isupper()):
                            text_file.write(tmpln + "\n")

                    text_file.close()
                    '''

                    for i in range(0, len(newlines)):
                        # line2 = strip_html(newlines[i]).lower()
                        # line2 = re.sub('\s+', ' ', line2.strip())
                        line2 = strip_html(newlines[i])
                        next_line = ""
                        prev_line = ""

                        if i > 0:
                            new_line = strip_html(newlines[i - 1]).lower()
                            if new_line != "" and new_line != " " and new_line != "  " and new_line != "   ":
                                new_line = re.sub('\s+', ' ', new_line.strip())
                                prev_line = new_line
                        if i < len(newlines) - 1:
                            new_line = strip_html(newlines[i + 1]).lower()
                            new_line = re.sub('\s+', ' ', new_line.strip())
                            next_line = new_line

                        row_to_write = [cik, company_name, form, filing_date, year, qtr]
                        keywords = []

                        if words[0] in line2:
                            num = [re.findall(r"(\d+)" + words[0], line2)]

                            if num is None:
                                num = [re.findall(r"(\d+)" + ' ' + words[0], line2)]

                            keywords.extend(num)
                            keywords.extend([prev_line + line2 + next_line])
                        else:
                            keywords.extend([''])
                            keywords.extend([''])

                        if words[1] in line2:
                            keywords.extend([line2.count(words[1])])
                            keywords.extend([prev_line + line2 + next_line])
                        else:
                            keywords.extend([''])
                            keywords.extend([''])

                        if words[2] in line2:
                            keywords.extend([line2.count(words[2])])
                            keywords.extend([prev_line + line2 + next_line])
                        else:
                            keywords.extend([''])
                            keywords.extend([''])

                        if words[3] in line2:
                            num = [re.findall(r"(\d+)" + words[3], line2)]

                            if num is None:
                                num = [re.findall(r"(\d+)" + ' ' + words[3], line2)]

                            keywords.extend(num)
                            keywords.extend([prev_line + line2 + next_line])
                        else:
                            keywords.extend([''])
                            keywords.extend([''])

                        if 'full-time employee' in line2 or 'full time employee' in line2:
                            keywords.extend([re.findall(r"(\d+)" + "full", line2)])
                            keywords.extend([prev_line + line2 + next_line])
                        else:
                            keywords.extend([''])
                            keywords.extend([''])

                        if keywords.count('') < 9:
                            row_to_write.extend(keywords)
                            row_to_write.extend([url3])
                            rows_to_write.append(row_to_write)

                    writecsv(rows_to_write)
