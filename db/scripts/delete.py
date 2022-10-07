from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

import argparse, os
from tqdm import tqdm
from lxml import etree

client = MongoClient(f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/')
collection = client.notesreview.notes

# Find all ids of the notes which are included in the current notes dump
def ids(file):
    ids = set()
    for event, element in tqdm(etree.iterparse(file, tag='note')):
        attributes = element.attrib
        ids.add(int(attributes['id']))
        element.clear()
    return ids

# Delete (or only print the ids of) all notes that are stored in the database but not included in the set of ids
def delete(ids, delete):
    for note in tqdm(collection.find({}, {'_id': True}).hint('_id_')):
        if note['_id'] not in ids:
            tqdm.write(str(note['_id']))
            if delete:
                collection.delete_one({'_id': note['_id']})

parser = argparse.ArgumentParser(description='Delete notes that are not included in the notes dump.')
parser.add_argument('file', type=str, help='path to the file which contains the notes dump')
parser.add_argument('--delete', default=False, action='store_true', help='confirm deletion of the notes')
args = parser.parse_args()

delete(ids(args.file), args.delete)
