import argparse
import datetime
import math
import os
import textwrap
import urllib.parse

import dateutil.parser
import requests
from dotenv import load_dotenv
from pymongo import DeleteOne, InsertOne, MongoClient, UpdateOne

load_dotenv()

client = MongoClient(f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/', tz_aware=True)
collection = client.notesreview.notes

DIRECTORY = os.path.dirname(os.path.realpath(__file__))


# Fills the database up by iterating over the OSM Notes API
# The current implementation is based on the last update of a note,
# all notes between now and another given date (the date of the last update) are imported into the database
def update(limit=100):
    # This variable is used in the while loop to ensure only notes of a specific timespan are fetched
    upper_bound = datetime.datetime.now(datetime.timezone.utc)
    # The start time of this function is used at the end to update the timestamp of the last update
    update_start_time = upper_bound
    with open(os.path.join(DIRECTORY, 'LAST_UPDATE.txt')) as file:
        last_update = dateutil.parser.parse(file.read())

    # Estimate a useful limit with a new note action every 15 seconds
    diff = (upper_bound - last_update).total_seconds()
    useful_limit = math.ceil(diff * (1 / 15))
    useful_limit = min(10000, useful_limit)

    # 0. Deleted 1. Added, 2. Updated, 3. Ignored
    all_stats = [0, 0, 0, 0]
    all_ignored = False

    # Either stop in case the stop date (i.e. the date of the last update) is exceeded or all notes are being ignored when inserting
    while upper_bound is not None and upper_bound > last_update and not all_ignored:
        url = build_url({
            'from': last_update.isoformat(),
            'to': upper_bound.isoformat(),
            'limit': str(limit)
        })
        response = requests.get(url).json()
        features = response['features']

        stats, oldest = insert(features)
        all_stats = [sum(x) for x in zip(all_stats, stats)]

        # Check whether all features were ignored, meaning there are no updates anymore
        all_ignored = stats[3] == len(features)
        upper_bound = oldest

    print(textwrap.dedent(f"""
    ----------------------------------------
    UPDATE SUMMARY
    --------------------
    Last update:    {last_update.isoformat(timespec='seconds')}
    End of update:  {update_start_time.isoformat(timespec='seconds')}
    Time in seconds since last update: {round(diff)}
    Expected a useful limit of {useful_limit} while {all_stats[0] + all_stats[1] + all_stats[2]} was actually needed
    --------------------
    Deleted {all_stats[0]} notes
    Added {all_stats[1]} new notes
    Updated {all_stats[2]} already existing notes
    Ignored {all_stats[3]} already existing notes
    ----------------------------------------
    """))

    with open(os.path.join(DIRECTORY, 'LAST_UPDATE.txt'), 'w') as file:
        file.write(update_start_time.isoformat(timespec='seconds'))
    # ---------------------------------------- #


def build_url(query={}):
    defaults = {
        'sort': 'updated_at',
        'closed': '-1',
        'limit': '100',
        # The start date needs to be specified because otherwise the value of the
        # 'to-parameter' has no effect (Use the begin of OpenStreetMap notes)
        'from': dateutil.parser.parse('2013-04-23T00:00:00')
    }
    host = 'https://api.openstreetmap.org/api/0.6/notes/search.json'
    url = host + '?' + urllib.parse.urlencode({**defaults, **query})
    return url


# Parse the comments and extract only the useful information
def parse(comments):
    for comment in comments:
        if 'date' in comment:
            comment['date'] = dateutil.parser.parse(comment['date'])
        if 'user_url' in comment:
            del comment['user_url']
        if 'html' in comment:
            del comment['html']
        if not comment['text']:
            del comment['text']
    return comments


# Loops through the provided list of notes and:
# - Adds notes if they are unknown
# - Updates notes if there is a different version
# - Ignores notes which are the same
def insert(features):
    operations = []
    deleted = 0
    inserted = 0
    updated = 0
    ignored = 0
    oldest = None

    for feature in features:
        comments = parse(feature['properties']['comments'])
        note = {
            '_id': feature['properties']['id'],
            'coordinates': feature['geometry']['coordinates'],
            'status': feature['properties']['status'],
            'updated_at': None if len(comments) == 0 else comments[-1]['date'],
            'comments': comments
        }
        query = {'_id': note['_id']}

        # If comments are invisible because of account deletion or other reasons,
        # a note might not contain any comments at all
        # see also https://github.com/openstreetmap/openstreetmap-website/issues/2146
        if len(note['comments']) == 0:
            # Notes without any comments are basically useless and should be deleted,
            # especially as the comments might have been removed by a moderator
            # and should not be visible to the public
            operations.append(DeleteOne(query))
            deleted += 1
            continue

        # TODO: This method of receiving the last updated note is not working reliable
        # as moderators might delete a comment which is just hidden to the users,
        # but still exists in the database so the API call to return the last updated notes
        # also includes these versions where some comments are missing

        # Try to find the oldest note based on the last update (this is needed for the next API request)
        # It also filters dates that differ a lot (the current threshold is at one hour (60 * 60 = 3600))
        # to prevent the issue mentioned above
        last_changed = note['comments'][-1]['date']
        if oldest is None or (last_changed < oldest and (oldest - last_changed).total_seconds() < (60 * 60)):
            oldest = last_changed

        document = collection.find_one(query)
        if document is None:
            # Note is not yet in the database, insert it
            operations.append(InsertOne(note))
            inserted += 1
        else:
            # Note is already stored in the database, the statement is only true if
            # "both dictionaries have the same (key, value) pairs (regardless of ordering)"
            # See https://docs.python.org/3/library/stdtypes.html#dict
            if note == document:
                # Note is the same as the one that is already saved, should be ignored
                ignored += 1
            else:
                # Note is different to the one that is already saved, needs to be updated
                # This may happen quite often as the notes dump seems to contain comments that are actually hidden
                # So after the initial import, a difference in the comments attached to a note may be detected
                operations.append(UpdateOne(query, {'$set': {
                    'status': note['status'],
                    'updated_at': note['updated_at'],
                    'comments': note['comments']
                }}))
                updated += 1

    if len(operations) != 0:
        result = collection.bulk_write(operations, ordered=False)
        if result.bulk_api_result['writeErrors']:
            client.events.errors.insert_one({
                'type': 'update_error',
                'timestamp': datetime.datetime.now(datetime.timezone.utc),
                'error': result.bulk_api_result['writeErrors']
            })
    return [deleted, inserted, updated, ignored], oldest


parser = argparse.ArgumentParser(description='Update notes between the last check and now.')
parser.add_argument('-l', '--limit', type=int, default=100, help='set the batch size limit (default: 100)')
args = parser.parse_args()

update(args.limit)
