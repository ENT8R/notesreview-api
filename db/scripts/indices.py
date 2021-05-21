from dotenv import load_dotenv
load_dotenv()

import json, os
import pymongo
client = pymongo.MongoClient(f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/')
db = client.notesreview

DIRECTORY = os.path.dirname(os.path.realpath(__file__))
RUN_IN_BACKGROUND = False

# Apply validation schemes (requires the collection to exist)
with open(os.path.join(DIRECTORY, '..', 'schema', 'schema.json')) as schema: schema = json.load(schema)
db.command({ 'collMod': 'notes', 'validator': schema['notesreview.notes'] })

# Create indices used for faster queries
db.notes.create_index([('updated_at', pymongo.DESCENDING)], name='created_at', background=RUN_IN_BACKGROUND)
db.notes.create_index([('comments.0.date', pymongo.DESCENDING)], name='updated_at', background=RUN_IN_BACKGROUND)
db.notes.create_index([('coordinates', pymongo.GEOSPHERE)], name='coordinates', background=RUN_IN_BACKGROUND)
db.notes.create_index('status', name='status', background=RUN_IN_BACKGROUND)
db.notes.create_index('comments.0.user', name='author', background=RUN_IN_BACKGROUND)
db.notes.create_index([('comments.text', pymongo.TEXT)], default_language='none', name='text', background=RUN_IN_BACKGROUND)
