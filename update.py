from pymongo import MongoClient
from pymongo import InsertOne, DeleteOne, UpdateOne
from pymongo.errors import BulkWriteError

import argparse, dateutil.parser, datetime
import math, requests, urllib.parse

from models.note import Note

client = MongoClient('mongodb://127.0.0.1:27017/')
# client.drop_database('notesreview') # WARNING: Use with care!
collection = client.notesreview.notes

# Fills the database up by iterating over the OSM Notes API
# The current implementation is based on the last update of a note,
# all notes between now and another given date (the date of the last update) are imported into the database
def update(limit=100):
    now = datetime.datetime.utcnow() # This variable is used by the while loop to ensure only notes of a specific timespan are fetched
    update_start_time = now # The start time of this function is used at the end to update the timestamp of the last update
    with open('LAST_UPDATE.txt') as file: stop_date = dateutil.parser.parse(file.read())

    diff = (now - stop_date).total_seconds()
    # Estimate a useful limit with one note action every fifteen seconds
    # TODO: figure out what might be a useful limit
    useful_limit = math.ceil(diff * (1 / 15)) # use min(10000, useful_limit) to get a limit not higher than the API limit of 10000
    print('Difference since last check in seconds: {} Expected useful limit: {}'.format(diff, useful_limit))

    all_stats = [0, 0, 0] # 1. Added, 2. Updated, 3. Ignored
    all_ignored = False

    # Either stop in case the stop date (i.e. the date of the last update) is exceeded or all notes are being ignored when inserting
    while now > stop_date and all_ignored == False:
        url = build_url({
            'from': stop_date.isoformat(),
            'to': now.isoformat(),
            'limit': str(limit)
        })
        print(url)
        response = requests.get(url).json()
        features = response['features']

        stats, oldest = insert(features)
        all_stats = [sum(x) for x in zip(all_stats, stats)]
        all_ignored = stats[2] == len(features) # Check whether all features were ignored, meaning there are no updates anymore
        now = oldest

    print(f"""
    --------------------
    UPDATE SUMMARY
    --------------------
    Added {all_stats[0]} new notes
    Updated {all_stats[1]} already existing notes
    Ignored {all_stats[2]} already existing notes
    This summary only affects notes updated after {now}
    """)

    # TODO: rather save this information in a MongoDB collection if possible
    with open('LAST_UPDATE.txt', 'w') as file: file.write(update_start_time.strftime("%Y-%m-%dT%H:%M:%S"))
    #### ---------------- ####

def build_url(query={}):
    defaults = {
        'sort': 'updated_at',
        'closed': '-1',
        'limit': '100',
        # The start date needs to be specified because otherwise the value of the 'to-parameter' has no effect
        'from': dateutil.parser.parse('2013-04-23T00:00:00') # Begin of OpenStreetMap notes
    }
    host = 'https://api.openstreetmap.org/api/0.6/notes/search.json'
    url = host + '?' + urllib.parse.urlencode({**defaults, **query})
    return url

# Loops through the provided list of notes and:
# - adds notes if they are unknown
# - updates notes if there is a different version
# - ignores notes which are the same
def insert(features):
    operations = []
    updated = 0
    ignored = 0
    oldest = None

    for feature in features:
        note = Note(feature)
        query = {'_id': note.id}

        # If comments are invisible because of account deletion or other reasons,
        # a note might not contain any comments at all
        # see also https://github.com/openstreetmap/openstreetmap-website/issues/2146
        if len(note.comments) == 0:
            # Notes without any comments are basically useless and should be deleted,
            # especially as the comments might have been removed by a moderator
            # and should not be visible to the public
            operations.append(DeleteOne(query))
            continue

        # TODO: this method of receiving the last updated note is not working reliable
        # as moderators might delete a comment which is just hidden to the users,
        # but still exists in the database so the API call to return the last updated notes
        # also includes these versions where some comments are missing
        # TODO: !URGENT! THIS SHOULD BE FIXED UPSTREAM => DON'T RETURN THESE NOTES WHEN FILTERING BY THE LAST CHANGE DATE

        # Try to find the oldest note based on the last update (this is needed for the next API request)
        # It also filters dates that differ a lot (the current threshold is at one hour (60 * 60 = 3600))
        last_changed = note.comments[-1]['date']
        if oldest is None or (last_changed < oldest and (oldest - last_changed).total_seconds() < (60 * 60)): oldest = last_changed

        document = collection.find_one(query)
        if document is None:
            # Note is not yet in the database, insert it
            operations.append(InsertOne(note.to_dict()))
        else:
            # Note is already in the database
            if note.to_dict() == document:
                # Note is the same as the one that is already saved, should be ignored
                ignored += 1
            else:
                # Note is different to the one that is already saved, needs to be updated
                operations.append(UpdateOne(query, {'$set': {
                    'status': note.status,
                    'updated_at': note.updated_at,
                    'comments': note.comments
                }}))
                updated += 1

    print('Executing {} operations'.format(len(operations)))
    result = collection.bulk_write(operations, ordered=False)
    print(result.bulk_api_result)
    return [result.inserted_count, updated, ignored], oldest

parser = argparse.ArgumentParser(description='Update notes between the last check and now.')
parser.add_argument('-l', '--limit', type=int, default=100, help='set the batch size limit (default: 100)')
args = parser.parse_args()
update(args.limit)
