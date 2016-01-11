import sys
import psycopg2
import os
from xml.etree import ElementTree as ET
from datetime import datetime
from time import time
import argparse

"""
HELPER FUNCTIONS
"""
def get_title(root):
    tag = '{http://purl.org/dc/elements/1.1/}title'
    els = root.findall(tag)
    return els.pop().text

def get_authors(root, sep='|'):
    tag = '{http://purl.org/dc/elements/1.1/}creator'
    els = root.findall(tag)
    authors = sep.join([el.text for el in els])
    return authors

def get_subject(root):
    tag = '{http://purl.org/dc/elements/1.1/}subject'
    subject = root.find(tag).text # just return the first one
    return subject

def get_abstract(root):
    tag = '{http://purl.org/dc/elements/1.1/}description'
    els = root.findall(tag)
    abstract = max([el.text for el in els], key=len) # shorter description is comment
    cleaned = abstract.replace('\n', ' ').strip()
    return cleaned

def get_arxivid(root):
    tag = '{http://purl.org/dc/elements/1.1/}identifier'
    els = root.findall(tag)
    for el in els:
        if el.text.startswith('http://arxiv.org/abs/'):
            return el.text.split('/').pop()
    return None

def get_date(root):
    tag = '{http://purl.org/dc/elements/1.1/}date'
    els = root.findall(tag)
    dates = [datetime.strptime(el.text, "%Y-%m-%d").date() for el in els]
    return (max(dates))

def create_schema(dbname='arxiv'):
    conn = psycopg2.connect(dbname=dbname)
    cur = conn.cursor()
    sql_create = """CREATE TABLE IF NOT EXISTS articles (
        index serial PRIMARY KEY,
        title text,
        authors text,
        subject text,
        abstract text,
        last_submitted date,
        arxiv_id text UNIQUE
    )"""
    cur.execute(sql_create)
    conn.commit()
    conn.close()


"""
This just combines the above helper functions
that fetch specific fields from xml.
Returns tuple of the needed fields
"""
def make_row(f_path):
    tree = ET.parse(f_path)
    root = tree.getroot()
    # get (title, authors, subject, abstract, date, arxiv_id)
    title = get_title(root)
    authors = get_authors(root)
    subject = get_subject(root)
    abstract = get_abstract(root)
    last_submitted = get_date(root)
    arxiv_id = get_arxivid(root)
    return (title, authors, subject, abstract, last_submitted, arxiv_id)


"""
Given a single xml file, inserts it into database
"""
def parse_and_insert_xml(f_path, dbname='arxiv'):
    with psycopg2.connect(dbname=dbname) as conn:
        with conn.cursor() as cur:
            # TODO: do batches of files
            query_template = "INSERT INTO articles (title, authors, subject, abstract, last_submitted, arxiv_id) VALUES (%s, %s, %s, %s, %s, %s)"
            values = make_row(f_path)
            insert_query = cur.mogrify(query_template, values)
            cur.execute(insert_query)
            conn.commit()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Parses xml files for fields and inserts into database')
    parser.add_argument('data_dir', help="Path to data folder")
    parser.add_argument('dbname', help="Name of postgres database")
    args = parser.parse_args()

    print(args.data_dir)
    print(args.dbname)

    # create the table if needed. default dbase name is arxiv. 
    create_schema(dbname=args.dbname)

    # data_dir = '/Users/Sepehr/dev/data-projects/arxiv-doc2vec-recommender/data/'
    filenames = os.listdir(args.data_dir)

    print("Embarking on processing %d files."%len(filenames))
    wins, fails = 0, 0
    init_time = time()
    for fname in filenames:
        f_path = args.data_dir + fname
        # print(f_path)
        try:
            parse_and_insert_xml(f_path, args.dbname)
            wins += 1
        except:
            fails += 1
            pass
        if (wins+fails)%500==0:
            # print("Last attempt: #%d -- %s"%((wins+fails), fname))
            print("Inserted %d documents. %d attempts failed"%(wins, fails))
            print("Seconds elapsed: %s"%(time() - init_time))

    print("Total documents inserted: %d"%(wins+fails))
    print("Documents failed: %d"%fails)
    print("Total time elapsed %s seconds"%(time() - init_time))