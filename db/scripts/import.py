from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

import argparse, os
import dateutil.parser
from tqdm import tqdm
from lxml import etree

client = MongoClient(f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/')
# client.drop_database('notesreview') # WARNING: Use with care!
collection = client.notesreview.notes

# Parses an XML file containing all notes and inserts them into the database
def insert(file):
    additions = []
    BATCH_SIZE = 20000 # Notes are inserted in batches of 20000
    i = 0

    for event, element in tqdm(etree.iterparse(file, tag='note')):
        attributes = element.attrib
        comments = parse(element)
        note = {
            '_id': int(attributes['id']),
            'coordinates': [float(attributes['lon']), float(attributes['lat'])],
            'status': 'closed' if 'closed_at' in attributes else 'open',
            'updated_at': comments[-1]['date'],
            'comments': comments
        }
        additions.append(note)
        element.clear()

        i += 1
        if i >= BATCH_SIZE:
            collection.insert_many(additions)
            additions = []
            i = 0

# Parse the comments and extract only the useful information
def parse(note):
    comments = []
    for element in note:
        attributes = element.attrib

        comment = {
            'date': dateutil.parser.parse(attributes['timestamp']),
            'action': attributes['action'],
            'text': element.text
        }
        if 'uid' in attributes: comment['uid'] = int(attributes['uid'])
        if 'user' in attributes: comment['user'] = attributes['user']
        if not element.text: del comment['text']

        comments.append(comment)
    return comments

parser = argparse.ArgumentParser(description='Import notes from a notes dump.')
parser.add_argument('file', type=str, help='path to the file which contains the notes dump')
args = parser.parse_args()
insert(args.file)
