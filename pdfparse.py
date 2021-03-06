# References
# https://towardsdatascience.com/extracting-headers-and-paragraphs-from-pdf-using-pymupdf-676e8421c467

import argparse, sys
import fitz
import pprint
import json
import re 

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Input file name')
    parser.add_argument('--output', help='Output file name')
    args = parser.parse_args()
    return args

def fonts(doc, granularity=False):
    """Extracts fonts and their usage in PDF documents.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param granularity: also use 'font', 'flags' and 'color' to discriminate text
    :type granularity: bool
    :rtype: [(font_size, count), (font_size, count}], dict
    :return: most used fonts sorted by count, font style information
    """
    styles = {}
    font_counts = {}

    for page in doc:
        blocks = page.getText("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # block contains text
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if granularity:
                            identifier = "{0}_{1}_{2}_{3}".format(s['size'], s['flags'], s['font'], s['color'])
                            styles[identifier] = {'size': s['size'], 'flags': s['flags'], 'font': s['font'],
                                                  'color': s['color']}
                        else:
                            identifier = "{0}".format(s['size'])
                            styles[identifier] = {'size': s['size'], 'font': s['font']}

                        font_counts[identifier] = font_counts.get(identifier, 0) + 1  # count the fonts usage

    font_counts = sorted(font_counts.items(), key=lambda item: item[1], reverse=True)

    if len(font_counts) < 1:
        raise ValueError("Zero discriminating fonts found!")

    return font_counts, styles

def font_tags(font_counts, styles):
    """Returns dictionary with font sizes as keys and tags as value.
    :param font_counts: (font_size, count) for all fonts occuring in document
    :type font_counts: list
    :param styles: all styles found in the document
    :type styles: dict
    :rtype: dict
    :return: all element tags based on font-sizes
    """
    p_style = styles[font_counts[0][0]]  # get style for most used font by count (paragraph)
    p_size = p_style['size']  # get the paragraph's size

    # sorting the font sizes high to low, so that we can append the right integer to each tag 
    font_sizes = []
    for (font_size, count) in font_counts:
        font_sizes.append(float(font_size))
    font_sizes.sort(reverse=True)

    # aggregating the tags for each font size
    idx = 0
    size_tag = {}
    for size in font_sizes:
        idx += 1
        if size == p_size:
            idx = 0
            size_tag[size] = '<p>'
        if size > p_size:
            size_tag[size] = '<h{0}>'.format(idx)
        elif size < p_size:
            size_tag[size] = '<s{0}>'.format(idx)

    return size_tag

def headers_para(doc, size_tag):
    """Scrapes headers & paragraphs from PDF and return texts with element tags.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param size_tag: textual element tags for each size
    :type size_tag: dict
    :rtype: list
    :return: texts with pre-prended element tags
    """
    header_para = []  # list with headers and paragraphs
    first = True  # boolean operator for first header
    previous_s = {}  # previous span

    for page in doc:
        blocks = page.getText("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # this block contains text

                # REMEMBER: multiple fonts and sizes are possible IN one block

                block_string = ""  # text found in block
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if s['text'].strip():  # removing whitespaces:
                            if first:
                                previous_s = s
                                first = False
                                block_string = size_tag[s['size']] + s['text']
                            else:
                                if s['size'] == previous_s['size']:

                                    if block_string and all((c == "|") for c in block_string):
                                        # block_string only contains pipes
                                        block_string = size_tag[s['size']] + s['text']
                                    if block_string == "":
                                        # new block has started, so append size tag
                                        block_string = size_tag[s['size']] + s['text']
                                    else:  # in the same block, so concatenate strings
                                        block_string += " " + s['text']

                                else:
                                    header_para.append(block_string)
                                    block_string = size_tag[s['size']] + s['text']

                                previous_s = s

                    # new block started, indicating with a pipe
                    block_string += "|"

                header_para.append(block_string)

    return header_para

def extract_data(data):
    """ splits each block with a header and para into a seperate list """
    index_list = []
    data_list = []
    for idx, val in enumerate(data):
        if '<h' in val:
            index_list = index_list + [idx]
        if idx == len(data)-1:
            index_list = index_list + [idx+1]
    
    for i,index in enumerate(index_list[:-1]):
        sub_list = data[index:index_list[i+1]]
        for i in sub_list:
            if not ('<h1>' in i or '<h2>' in i or '<p>' in i):
                sub_list.remove(i)
        data_list.append(sub_list)
    
    return data_list

def data_tojson(data_list):
    """converts the list of lists of header-para blocks to logical json data
    all logic specific to extract data from the given file """

    json_data = {}
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'] 
    for data in data_list:
        if '<h1>' in data[0]: # processing main header
            json_data['name'] = data[0][4:data[0].find('|')] # name is the first element in main header
            json_data['phone'] = data[2].split('|')[0][3:].replace(' ', '') # phone is the first part of second element
            json_data['email'] = data[2].split('|')[1].replace(' ', '')  # email is the second part of second element          
            json_data['address'] = data[3][3:data[3].find('|')] # address is the third element

        elif '<h2>' in data[0]: # processing subheaders
            key = data[0][4:data[0].find('|')]
            json_data[key] = {}
            value = ''
            skills_list = []
            date_period = 1 
            first_date = True
            for idx,i in enumerate(data[1:]):
                if '<p>' in i:
                    if key == 'Skills & Interests': # additional granularity added for  Skills 
                        skills_list = i[3:].split('|')
                        for skill in skills_list[:-1]:
                            skill_type = skill.split(':')[0]
                            skill_content = skill.split(':')[1]
                            json_data[key][skill_type] = skill_content
                    else:
                        if any(month in i for month in months):
                            if first_date:
                                first_date = False
                                json_data[key][date_period] = {}
                            else:
                                json_data[key][date_period]['details'] = value  
                                value = '' 
                                date_period = date_period + 1
                                json_data[key][date_period] = {}

                            # extracting date value for all sub headers
                            matches = re.findall('((\d{2}|January|Jan|February|Feb|March|Mar|April|Apr|May|May|June|Jun|July|Jul|August|Aug|September|Sep|October|Oct|November|Nov|December|Dec)[\/ ]\d{2,4})', i)
                            if len(matches) > 1:
                                date = matches[0][0] + ' - ' + matches[1][0]
                                json_data[key][date_period]['date'] = date
                                i = i.replace(matches[0][0], '')
                                i = i.replace(matches[1][0], '')
                            else:
                                date = matches[0][0]
                                json_data[key][date_period]['date'] = date
                                i = i.replace(matches[0][0], '')

                        value = value + i.replace('|', '').replace('    ','')[3:]

                if idx == len(data)-2 and key != 'Skills & Interests':
                    if date_period not in json_data[key]:
                        json_data[key][date_period] = {}
                    json_data[key][date_period]['details'] = value
                    
    return json_data

def main():
    args = get_args()
    filename = args.input
    doc = fitz.open(filename)
    font_counts, styles = fonts(doc)
    tags = font_tags(font_counts, styles)
    data = headers_para(doc, tags)
    extracted_data = extract_data(data)
    json_data = data_tojson(extracted_data)
    
    output_file = args.output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

if __name__=="__main__":
    main() 

