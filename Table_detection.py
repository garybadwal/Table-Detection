import os
import cv2
import shutil
import pdfplumber
from fuzzywuzzy import fuzz
from pdf2image import convert_from_path
# from sentence_transformers import SentenceTransformer, util

# diffrent table headers for diffrent files define your new one in "CONSTANT.PY" file
from constants import USER_TABLE_HEADER, USER_TABLE_HEADER2, USER_TABLE_HEADER3, USER_TABLE_HEADER4

# set your table headers here
TABLE_HEADER = USER_TABLE_HEADER2

# set file path in which you want to find the table
FILE_PATH = "/home/gary/Downloads/KT/20003.pdf"

def convert_to_image(pdf_file: str) -> str:
    """ convert the PDF file to images
    fuction take input as pdf file path
    convert it to image object
    save file to a folder that is created in this function "pdf_to_image"
    in the current working directory
    and return the folder path as output.
    """

    page = 0
    
    current_dir = os.getcwd()
    image_path = current_dir+'/test/'

    try:
        os.mkdir(image_path)
    except:
        shutil.rmtree(image_path, ignore_errors=False, onerror=None)
        os.mkdir(image_path)
    
    for image in convert_from_path(pdf_file):
        image.save(image_path+'page_'+ str(page) +'.jpg', 'JPEG')
        page+=1
    
    return image_path

def get_words(pdf_file: str) -> list:

    """Read PDF file pages as image and get a list of words

    Returns:
        list: list of dict ({
            pageNumber,
            list of words in that page
        })
    """

    result = []
    page_documents = convert_from_path(pdf_file)
    with pdfplumber.open(pdf_file) as pdf:
        total_pages = len(pdf.pages)
        output_by_page = {}
        for i in range(total_pages):
            # extract text if original pdf page
            pdf_page = pdf.pages[i]
            pdf_page_image = page_documents[i]
            pdf_image_width, pdf_image_height = pdf_page_image.size
            w_scale, h_scale = (pdf_image_width/pdf_page.width), (pdf_image_height/pdf_page.height)
            ocr_words = []
            words = pdf_page.extract_words()
            if words:

                for word_dict in words:
                    ocr_words.append((
                        ((word_dict['x0']*w_scale), (word_dict['top']*h_scale),  (word_dict['x1'])*w_scale, (word_dict['bottom']*h_scale)),
                        word_dict['text'],
                        100
                    ))
            
            result.append({
                'pageNumber': i,
                'words': ocr_words,
            })
    
    return result

def listleftIndex(val: list) -> int:

    """Get the left index of word (list)

    Returns:
        int: int
    """

    return val[0][0]

def listtopIndex(val: list) -> int:

    """Get the top index of word (list)

    Returns:
        int: int
    """

    return val[0][1]

def dicttopIndex(val: dict) -> int:
    return val.get('top')

def get_lines(page_words: list) -> list:

    """Generate lines from the page word

    Returns:
        list: list of dict ({
            pageNumber,
            list of lines
        })
    """

    result = []

    for page in page_words:
        lines = []
        words  = page.get("words")
        while words != []:
            words.sort(key=listtopIndex)
            words.sort(key=listleftIndex)
            
            line = {
                'text': "",
                'top': 0,
                'bottom': 0,
            }

            word_left = words[0][0][0]
            word_top = words[0][0][1]
            word_bottom = words[0][0][3]

            word_height = (word_bottom-word_top)

            line_top = word_top-(word_height/3)

            line_bottom = word_bottom+(word_height/3)

            line_text = words[0][1]

            words.remove(words[0])
            
            for word in words:
                selected_word_top = word[0][1]
                selected_word_bottom = word[0][3]
                selected_word_left = word[0][0]
                if selected_word_top+15>=line_top and selected_word_bottom-15<=line_bottom and selected_word_left>=word_left:
                    line_text += word[1]
                    words.remove(word)
            
            line["text"] = line_text
            line["top"] = line_top
            line["bottom"] = line_bottom

            lines.append(line)
        
        result.append({
            "pageNumber": page.get("pageNumber"),
            "lines": lines,
        })
    
    return result

def get_line_match(page_lines: list) -> list:

    """add confidance score of each line matched to the header

    Returns:
        list: list of dict ({
            pageNumber,
            list of lines
        })
    """

    # model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    label_attributes = "".join(TABLE_HEADER).lower()
    for page in page_lines:
        
        lines = page.get("lines")

        for line in lines:
            text = line.get("text").lower()
            # embeddings1 = model.encode(text, convert_to_tensor=True)
            # embeddings2 = model.encode(label_attributes, convert_to_tensor=True)
            # cosine_scores = util.cos_sim(embeddings1, embeddings2)
            # breakpoint()
            # # print(text+'\n'+label_attributes+'\n'+str(fuzz.partial_ratio(label_attributes,text)),end="\n\n")
            line.update({"conf": fuzz.ratio(label_attributes,text)})
    
    return page_lines

def get_table_top(page_lines: list) -> list:

    """get the top with the max Confidance score as the top

    Returns:
        list: list of dict({
            pageNumber,
            table tops in that pageS
        })
    """

    result = []

    tops = []

    for page in page_lines:
        lines = page.get("lines")
        for line in lines:
            if line.get('conf')>60:
                tops.append(line.get("top"))
                print(line, end="\n\n")
        
        if tops:
            result.append({
                'page': page.get("pageNumber"),
                'table_tops': [max(tops)],
            })
    
    return result

def get_table_bottom(page_lines: list, table_header_top: list) -> list:

    """get the bottom with the avg distance in the lines

    Returns:
        list: list of dict({
            pageNumber,
            table bottom in that page
        })
    """

    result = []

    new_lines = []

    for page in page_lines:
        lines = page.get("lines")
        avg_distance = 0

        tops = table_header_top[page.get("pageNumber")]

        for top in tops.get('table_tops'):
            bottom = 0
            temp_avg_distance = []
            for line in lines:
                if line.get('top')>= top:
                    new_lines.append(line)
            
            new_lines.sort(key=dicttopIndex)
            
            for idx in range(0, len(new_lines)-1):
                line1 = new_lines[idx]
                line2 = new_lines[idx+1]

                temp_avg_distance.append(line2.get('top')-line1.get('bottom'))
            
            for dis in temp_avg_distance:
                avg_distance+=dis
            
            avg_distance = avg_distance//len(new_lines)

            print("AVG DIS :: "+str(avg_distance))

            for idx in range(0, len(new_lines)-1):
                line1 = new_lines[idx]
                line2 = new_lines[idx+1]

                distance = line2.get('top')-line1.get('bottom')

                if avg_distance>0:
                    if distance>avg_distance:
                        bottom = line1.get('bottom')
                else:
                    if distance<avg_distance:
                        bottom = line1.get('bottom')
            
            result.append({
                'pageNumber': page.get("pageNumber"),
                'tables':[{
                   'top': top,
                   'bottom': bottom
                }]
            })

    return result

def crop_image(page_list: list):

    """Crop the image with table top and table bottom
    """

    for page in page_list:
        tables = page.get("tables")
        img = cv2.imread('test/page_'+str(page.get("pageNumber"))+'.jpg')
        table_idx = 0
        for table in tables:
            top = int(table.get('top'))
            bottom = int(table.get("bottom"))
            image = img[top:bottom, 0:img.shape[1]]
            cv2.imwrite('test/page_'+str(page.get("pageNumber"))+'_table_'+str(table_idx)+'.jpg', image)
            table_idx += 1
    

if __name__ == "__main__":

    convert_to_image(pdf_file=FILE_PATH)

    words = get_words(FILE_PATH)

    page_lines = get_lines(words)

    matches = get_line_match(page_lines)

    table_header_top = get_table_top(matches)
    
    table = get_table_bottom(matches, table_header_top)

    crop_image(table)