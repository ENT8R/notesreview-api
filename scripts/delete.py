import argparse
import os

from dotenv import load_dotenv
from lxml import etree
from pymongo import MongoClient
from tqdm import tqdm

from . import iteration

load_dotenv()

client = MongoClient(
    f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/?authSource=notesreview'
)
collection = client.notesreview.notes


# Find all ids of the notes which are included in the current notes dump
def ids(file):
    ids = set()
    last_id = 0

    def process_element(element):
        nonlocal ids, last_id

        attributes = element.attrib
        id = int(attributes['id'])
        last_id = id
        ids.add(id)

    iteration.fast_iter(
        tqdm(etree.iterparse(file, tag='note', events=('end',))),
        process_element,
    )
    return ids, last_id


# Delete (or only print the ids of) all notes that are stored in the database but not included in the set of ids
def delete(ids_in_dump, last_id, delete):
    ids_in_db = set()
    # Iterate over all documents with an id lower than the last id of the notes dump
    for note in tqdm(
        collection.find({}, {'_id': True}).max([('_id', last_id)]).hint('_id_')
    ):
        if note['_id'] not in ids_in_dump:
            # Add the id to the set if the note is in the database but not the dump
            ids_in_db.add(note['_id'])
            tqdm.write(str(note['_id']))
        else:
            # Remove the id if the note is in the database and the dump
            ids_in_dump.remove(note['_id'])

    # ids_in_dump(_but_not_in_db) contains all notes that are in the dump but not in the database,
    # ids_in_db(_but_not_in_dump) contains all notes that are in the database but not in the dump
    tqdm.write(
        f'There are currently {len(ids_in_dump)} notes that are in the dump but not in the database'
    )
    tqdm.write(
        f'There are currently {len(ids_in_db)} notes that are in the database but not in the dump'
    )

    if delete:
        # Delete all notes that are currently in the database but not in the dump
        result = collection.delete_many(
            {'_id': {'$in': list(ids_in_db)}}, hint='_id_'
        )
        tqdm.write(
            f'Deleted {result.deleted_count} notes which are not present in the notes dump anymore'
        )


parser = argparse.ArgumentParser(
    description='Delete notes that are not included in the notes dump.'
)
parser.add_argument(
    'file', type=str, help='path to the file which contains the notes dump'
)
parser.add_argument(
    '--delete',
    default=False,
    action='store_true',
    help='confirm deletion of the notes',
)
args = parser.parse_args()

delete(*ids(args.file), args.delete)
