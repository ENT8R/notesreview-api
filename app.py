from db.query import Filter

import orjson
from motor.motor_asyncio import AsyncIOMotorClient

from sanic import Sanic
from sanic.response import raw, json

app = Sanic(__name__)

@app.before_server_start
async def setup(app, loop):
    client = AsyncIOMotorClient('mongodb://127.0.0.1:27017', io_loop=loop)
    app.ctx.client = client
    app.ctx.db = client.notesreview

@app.before_server_stop
async def shutdown(app, loop):
    app.ctx.client.close()

@app.get('/search')
async def search(request):
    # Figure out how to sort the results
    sort_by = request.args.get('sort_by', 'updated_at')
    if sort_by not in ['updated_at', 'created_at']:
        return json({'error': 'sort must be one of [updated_at, created_at]'}, status=400)
    sort_by = 'comments.0.date' if sort_by == 'created_at' else 'updated_at'

    order = request.args.get('order', 'descending')
    if order not in ['desc', 'descending', 'asc', 'ascending']:
        return json({'error': 'order must be one of [desc, descending, asc, ascending]'}, status=400)
    order = 1 if order in ['asc', 'ascending'] else -1
    sort = [(sort_by, order)]

    #----------------------------------------#
    filter = (Filter(sort_by)
                .query(request.args.get('query')) # A word or sentence which can be found in the comments
                .status(status = request.args.get('status')) # Whether the note is already closed or still open
                .anonymous(request.args.get('anonymous', 'true')) # Whether anonymous notes should be included in the results
                .author(request.args.get('author')) # Filter only notes created by the specified user
                .after(request.args.get('after', None)) # Filter only notes updated/created after this date
                .before(request.args.get('before', None)) # Filter only notes updated/created before this date
                .comments(request.args.get('comments', None)) # Filters the amount of comments on a note
                .build())
    #----------------------------------------#

    # Set the correct limit
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000
    limit = int(request.args.get('limit', DEFAULT_LIMIT))
    if limit > MAX_LIMIT:
        return json({'error': 'Limit must not be higher than %d' % MAX_LIMIT}, status=400)
    if limit == 0:
        limit = DEFAULT_LIMIT # Prevent that a limit of 0 is treated as no limit at all

    cursor = app.ctx.db.notes.find(filter).limit(limit).sort(sort)
    result = []
    async for document in cursor: result.append(document)
    return json(result, dumps=orjson.dumps)
