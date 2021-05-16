import os
from dotenv import load_dotenv
load_dotenv()

from db.query import Filter, Sort

import orjson
from motor.motor_asyncio import AsyncIOMotorClient

from sanic import Sanic
from sanic.response import raw, json

app = Sanic(__name__)
settings = dict(
    DEFAULT_LIMIT = 50,
    MAX_LIMIT = 100,
    DB_USER = os.environ.get('DB_USER'),
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
)
app.config.update(settings)

@app.before_server_start
async def setup(app, loop):
    client = AsyncIOMotorClient(f'mongodb://{app.config.DB_USER}:{app.config.DB_PASSWORD}@127.0.0.1:27017', io_loop=loop)
    app.ctx.client = client
    app.ctx.db = client.notesreview

@app.before_server_stop
async def shutdown(app, loop):
    app.ctx.client.close()

@app.get('/api/search')
async def search(request):
    try:
        sort = Sort().by(request.args.get('sort_by', 'updated_at')).order(request.args.get('order', 'descending')).build()
        filter = (Filter(sort)
                    .query(request.args.get('query')) # A word or sentence which can be found in the comments
                    .status(status = request.args.get('status')) # Whether the note is already closed or still open
                    .anonymous(request.args.get('anonymous', 'true')) # Whether anonymous notes should be included in the results
                    .author(request.args.get('author')) # Filter only notes created by the specified user
                    .after(request.args.get('after', None)) # Filter only notes updated/created after this date
                    .before(request.args.get('before', None)) # Filter only notes updated/created before this date
                    .comments(request.args.get('comments', None)) # Filters the amount of comments on a note
                    .build())
    except ValueError as error:
        return json({'error': str(error)}, status=400)

    #----------------------------------------#

    limit = int(request.args.get('limit', app.config.DEFAULT_LIMIT))
    if limit > app.config.MAX_LIMIT:
        return json({'error': f'Limit must not be higher than {app.config.MAX_LIMIT}'}, status=400)
    # Prevent that a limit of 0 is treated as no limit at all
    if limit == 0:
        limit = app.config.DEFAULT_LIMIT

    cursor = app.ctx.db.notes.find(filter).limit(limit).sort(*sort)
    result = []
    async for document in cursor: result.append(document)
    return json(result, dumps=orjson.dumps)
