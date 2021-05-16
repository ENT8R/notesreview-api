import os
from dotenv import load_dotenv
load_dotenv()

import pymongo
client = pymongo.MongoClient(f'mongodb://{os.environ.get("DB_USER")}:{os.environ.get("DB_PASSWORD")}@127.0.0.1:27017/')
db = client.notesreview

RUN_IN_BACKGROUND = False

db.notes.create_index([('updated_at', pymongo.DESCENDING)], name='created_at', background=RUN_IN_BACKGROUND)
db.notes.create_index([('comments.0.date', pymongo.DESCENDING)], name='updated_at', background=RUN_IN_BACKGROUND)

db.notes.create_index([('coordinates', pymongo.GEOSPHERE)], name='coordinates', background=RUN_IN_BACKGROUND)

db.notes.create_index('status', name='status', background=RUN_IN_BACKGROUND)

db.notes.create_index('comments.0.user', name='author', background=RUN_IN_BACKGROUND)

db.notes.create_index([('comments.text', pymongo.TEXT)], default_language='none', name='text', background=RUN_IN_BACKGROUND)
