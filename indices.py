import pymongo
client = pymongo.MongoClient('mongodb://127.0.0.1:27017/')
collection = client.notesreview.notes

RUN_IN_BACKGROUND = False

collection.create_index([('updated_at', pymongo.DESCENDING)], name='created_at', background=RUN_IN_BACKGROUND)
collection.create_index([('comments.0.date', pymongo.DESCENDING)], name='updated_at', background=RUN_IN_BACKGROUND)

collection.create_index([('coordinates', pymongo.GEOSPHERE)], name='coordinates', background=RUN_IN_BACKGROUND)

collection.create_index('status', name='status', background=RUN_IN_BACKGROUND)

collection.create_index('comments.0.user', name='author', background=RUN_IN_BACKGROUND)
# TODO: this text index is way too big and slows everything down
# collection.create_index([('comments.text', pymongo.TEXT)], default_language='none', name='text', background=RUN_IN_BACKGROUND)
