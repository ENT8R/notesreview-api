import os
from textwrap import dedent

import orjson
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic
from sanic.response import json
from sanic_ext import openapi

from api.models.note import Note
from api.query import Filter, Sort

load_dotenv()

app = Sanic(__name__)
settings = dict(
    DEFAULT_LIMIT = 50,
    MAX_LIMIT = 100,
    DB_USER = os.environ.get('DB_USER'),
    DB_PASSWORD = os.environ.get('DB_PASSWORD'),
    DB_HOST = os.environ.get('DB_HOST'),
    CORS_ORIGINS = '*',
    CORS_ALWAYS_SEND = False
)
app.config.update(settings)

app.ext.openapi.describe(
    "notesreview-api",
    version="0.1.0",
    description=dedent(
        """
        # Information
        This API is still subject to change, especially the behavior of the `query` parameter might change in the future,
        because right now the possibilities are still a little bit limited.
        """
    )
)

@app.before_server_start
async def setup(app, loop):
    client = AsyncIOMotorClient(f'mongodb://{app.config.DB_USER}:{app.config.DB_PASSWORD}@{app.config.DB_HOST}:27017', io_loop=loop)
    app.ctx.client = client
    app.ctx.db = client.notesreview

@app.before_server_stop
async def shutdown(app, loop):
    app.ctx.client.close()

@app.get('/api/search')
@openapi.description('Search and filter all notes in the database')
@openapi.parameter('query', openapi.String(description=dedent(
    """
    A word or sentence which can be found in the comments.
    To find an exact occurence of a word or sentence, wrap it in quotation marks `"{query}"`.
    Single words can be excluded from the result by prepending a dash `-` to the word.
    Spaces and other delimiters like dots are currently treated as a logical OR,
    though this will likely change in the future.
    """), default=None, required=False))
@openapi.parameter('bbox', openapi.String(description='A pair of coordinates specifying a rectangular box where all results are located in.', example='-87.6955,41.8353,-87.5871,41.9170', default=None))
@openapi.parameter('status', openapi.String(description='The current status of the note', enum=('all', 'open', 'closed'), default='all'))
@openapi.parameter('anonymous', openapi.String(description='Whether anonymous notes should be included inclusively, excluded or included exclusively in the results', enum=('include', 'hide', 'only'), default='include'))
@openapi.parameter('author', openapi.String(description='Name of the user who opened the note', default=None))
@openapi.parameter('after', openapi.DateTime(description='Only return notes updated or created after this date', default=None, example='2020-03-13T10:20:24'))
@openapi.parameter('before', openapi.DateTime(description='Only return notes updated or created before this date', default=None, example='2020-05-11T07:10:45'))
@openapi.parameter('comments', openapi.Integer(description='Filters the amount of comments on a note', minimum=0, default=None))
@openapi.parameter('sort_by', openapi.String(description='Sort notes either by the date of the last update or their creation date', enum=('updated_at', 'created_at'), default='updated_at'))
@openapi.parameter('order', openapi.String(description='Sort notes either in ascending or descending order', enum=('descending', 'desc', 'ascending', 'asc'), default='descending'))
@openapi.parameter('limit', openapi.Integer(description='Limit the amount of notes to return', minimum=1, maximum=app.config.MAX_LIMIT, default=app.config.DEFAULT_LIMIT))
@openapi.response(200, openapi.Array(items=Note, uniqueItems=True), 'The response is an array containing the notes with the requested information')
@openapi.response(400, openapi.Object(properties={
    'error': openapi.String()
}), 'In case one of the parameters is invalid, the response contains the error message')
async def search(request):
    try:
        sort = Sort().by(request.args.get('sort_by', 'updated_at')).order(request.args.get('order', 'descending')).build()
        filter = (Filter(sort)
                    .query(request.args.get('query'))
                    .bbox(request.args.get('bbox'))
                    .status(request.args.get('status'))
                    .anonymous(request.args.get('anonymous'))
                    .author(request.args.get('author'))
                    .after(request.args.get('after', None))
                    .before(request.args.get('before', None))
                    .comments(request.args.get('comments', None))
                    .build())
    except ValueError as error:
        return json({'error': str(error)}, status=400)

    #----------------------------------------#

    # Apply the default limit in case the argument could not be parsed (e.g. for limit=NaN)
    try:
        limit = int(request.args.get('limit', app.config.DEFAULT_LIMIT))
    except ValueError as error:
        limit = app.config.DEFAULT_LIMIT

    if limit > app.config.MAX_LIMIT:
        return json({'error': f'Limit must not be higher than {app.config.MAX_LIMIT}'}, status=400)

    # Prevent that a limit of 0 is treated as no limit at all
    if limit == 0:
        limit = app.config.DEFAULT_LIMIT

    cursor = app.ctx.db.notes.find(filter).limit(limit).sort(*sort)
    result = []
    async for document in cursor:
        result.append(document)
    return json(result, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)
