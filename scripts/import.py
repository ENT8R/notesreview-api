import argparse
import datetime
import os
import textwrap

import dateutil.parser
import iteration
from dotenv import load_dotenv
from lxml import etree
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

load_dotenv()

client = MongoClient(
    f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/?authSource=notesreview',
    tz_aware=True,
)
collection = client.notesreview.notes

DIRECTORY = os.path.dirname(os.path.realpath(__file__))


# Parses an XML file containing all notes and inserts them into the database
def insert(file):
    # Notes are inserted/updated in batches of 50000
    BATCH_SIZE = 50000

    operations = []
    # 0. Deleted 1. Added, 2. Updated, 3. Matched
    all_stats = [0, 0, 0, 0]
    last_id = 0

    def process_element(element):
        nonlocal operations, all_stats, last_id

        try:
            attributes = element.attrib
            id = int(attributes['id'])
            last_id = id
            comments = parse(element)
            note = {
                '_id': id,
                'coordinates': [
                    float(attributes['lon']),
                    float(attributes['lat']),
                ],
                'status': 'closed' if 'closed_at' in attributes else 'open',
                'updated_at': comments[-1]['date'],
                'comments': comments,
            }
        except Exception:
            tqdm.write(f'Failed to parse note with the id {id}')
            return

        operations.append(
            UpdateOne(
                {'_id': id},
                {
                    '$set': {
                        'status': note['status'],
                        'updated_at': note['updated_at'],
                        'comments': note['comments'],
                    },
                    '$setOnInsert': {
                        'coordinates': note['coordinates'],
                    },
                },
                upsert=True,
                hint='_id_',
            )
        )

        if len(operations) >= BATCH_SIZE:
            stats = write(operations)
            all_stats = [sum(x) for x in zip(all_stats, stats)]
            operations = []

    iteration.fast_iter(
        tqdm(etree.iterparse(file, tag='note', events=('end',))),
        process_element,
    )

    if len(operations) > 0:
        stats = write(operations)
        all_stats = [sum(x) for x in zip(all_stats, stats)]
        operations = []

    # Use the creation date of the last note in the dump as the timestamp of the last import
    last_date = collection.find_one({'_id': last_id})['comments'][0]['date']
    with open(os.path.join(DIRECTORY, 'LAST_IMPORT.txt'), 'w') as file:
        file.write(last_date.isoformat(timespec='seconds'))

    tqdm.write(
        textwrap.dedent(
            f"""
            ----------------------------------------
            IMPORT SUMMARY
            --------------------
            Deleted {all_stats[0]} notes
            Added {all_stats[1]} new notes
            Updated {all_stats[2]} already existing notes
            Matched {all_stats[3]} notes
            ----------------------------------------
            Please make sure to run the update script at least until {last_date.isoformat(timespec='seconds')}
            to import all changes between the creation of the notes dump and now.
            """
        )
    )


# Write operations to the database using the bulk write feature
def write(operations):
    result = collection.bulk_write(operations, ordered=False)
    if result.bulk_api_result['writeErrors']:
        client.events.errors.insert_one(
            {
                'type': 'import_error',
                'timestamp': datetime.datetime.now(datetime.timezone.utc),
                'error': result.bulk_api_result['writeErrors'],
            }
        )
    return [
        result.bulk_api_result['nRemoved'],
        result.bulk_api_result['nInserted'],
        result.bulk_api_result['nModified'],
        result.bulk_api_result['nMatched'],
    ]


# Parse the comments and extract only the useful information
def parse(note):
    comments = []
    for element in note:
        attributes = element.attrib

        comment = {
            'date': dateutil.parser.parse(attributes['timestamp']),
            'action': attributes['action'],
            'text': element.text,
        }
        if 'uid' in attributes:
            comment['uid'] = int(attributes['uid'])
        if 'user' in attributes:
            comment['user'] = attributes['user']
        if not element.text:
            del comment['text']

        comments.append(comment)
    return comments


parser = argparse.ArgumentParser(description='Import notes from a notes dump.')
parser.add_argument(
    'file', type=str, help='path to the file which contains the notes dump'
)
args = parser.parse_args()

insert(args.file)
