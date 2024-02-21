import os
from textwrap import dedent

import orjson
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic
from sanic.response import json
from sanic.views import HTTPMethodView
from sanic_ext import openapi

from api.models.note import Note
from api.query import Filter, Sort

load_dotenv()

app = Sanic(__name__)
settings = dict(
    DEFAULT_LIMIT=50,
    MAX_LIMIT=250,
    DB_USER=os.environ.get('DB_USER'),
    DB_PASSWORD=os.environ.get('DB_PASSWORD'),
    DB_HOST=os.environ.get('DB_HOST'),
    CORS_ORIGINS='*',
    CORS_ALWAYS_SEND=False
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


class Search(HTTPMethodView):
    @openapi.description('Search and filter all notes in the database')
    @openapi.parameter('query', openapi.String(description=dedent(
        """
        A word or sentence which can be found in the comments.
        To find an exact occurence of a word or sentence, wrap it in quotation marks `"{query}"`.
        Single words can be excluded from the result by prepending a dash `-` to the word.
        Spaces and other delimiters like dots are currently treated as a logical OR,
        though this will likely change in the future.
        """), default=None, required=False))
    @openapi.parameter('bbox', openapi.String(description='A pair of coordinates specifying a rectangular box where all results are located in', example='-87.6955,41.8353,-87.5871,41.9170', default=None))
    @openapi.parameter('polygon', openapi.String(description='A GeoJSON polygon specifying a region where all results are located in', default=None))
    @openapi.parameter('status', openapi.String(description='The current status of the note', enum=('all', 'open', 'closed'), default='all'))
    @openapi.parameter('anonymous', openapi.String(description='Whether anonymous notes should be included inclusively, excluded or included exclusively in the results', enum=('include', 'hide', 'only'), default='include'))
    @openapi.parameter('author', openapi.String(description='Name of the user who opened the note, searching for multiple users is possible by separating them with a comma', default=None))
    @openapi.parameter('user', openapi.String(description='Name of any user who commented on the note, searching for multiple users is possible by separating them with a comma', default=None))
    @openapi.parameter('after', openapi.DateTime(description='Only return notes updated or created after this date', default=None, example='2020-03-13T10:20:24'))
    @openapi.parameter('before', openapi.DateTime(description='Only return notes updated or created before this date', default=None, example='2020-05-11T07:10:45'))
    @openapi.parameter('comments', openapi.Integer(description='Filters the amount of comments on a note', minimum=0, default=None))
    @openapi.parameter('commented', openapi.String(description='Whether commented notes should be included inclusively, excluded or included exclusively in the results', enum=('include', 'hide', 'only'), default='include'))
    @openapi.parameter('sort_by', openapi.String(description='Sort notes either by no criteria, the date of the last update or their creation date', enum=('none', 'updated_at', 'created_at'), default='updated_at'))
    @openapi.parameter('order', openapi.String(description='Sort notes either in ascending or descending order', enum=('descending', 'desc', 'ascending', 'asc'), default='descending'))
    @openapi.parameter('limit', openapi.Integer(description='Limit the amount of notes to return', minimum=1, maximum=app.config.MAX_LIMIT, default=app.config.DEFAULT_LIMIT))
    @openapi.response(200, openapi.Array(items=Note, uniqueItems=True), 'The response is an array containing the notes with the requested information')
    @openapi.response(400, openapi.Object(properties={
        'error': openapi.String()
    }), 'In case one of the parameters is invalid, the response contains the error message')
    async def get(self, request):
        try:
            sort, filter, limit = self.parse(request.args)
        except ValueError as error:
            return json({'error': str(error)}, status=400)

        return await self.search(sort, filter, limit)

    async def post(self, request):
        try:
            sort, filter, limit = self.parse(request.json)
        except ValueError as error:
            return json({'error': str(error)}, status=400)

        return await self.search(sort, filter, limit)

    def parse(self, data):
        sort = Sort().by(data.get('sort_by', 'updated_at')).order(data.get('order', 'descending')).build()
        filter = (Filter(sort)
                  .query(data.get('query'))
                  .bbox(data.get('bbox'))
                  .polygon(data.get('polygon'))
                  .status(data.get('status'))
                  .anonymous(data.get('anonymous'))
                  .author(data.get('author'))
                  .user(data.get('user'))
                  .after(data.get('after', None))
                  .before(data.get('before', None))
                  .comments(data.get('comments', None))
                  .commented(data.get('commented'))
                  .build())
        limit = data.get('limit', app.config.DEFAULT_LIMIT)

        return sort, filter, limit

    async def search(self, sort, filter, limit):
        # Apply the default limit in case the argument could not be parsed (e.g. for limit=NaN)
        try:
            limit = int(limit)
        except ValueError:
            limit = app.config.DEFAULT_LIMIT

        if limit > app.config.MAX_LIMIT:
            return json({'error': f'Limit must not be higher than {app.config.MAX_LIMIT}'}, status=400)

        # Prevent that a limit of 0 is treated as no limit at all
        if limit == 0:
            limit = app.config.DEFAULT_LIMIT

        cursor = app.ctx.db.notes.find(filter).limit(limit)
        # Queries are faster if the sorting is not explicitly specified (if desired)
        if sort[0] is not None:
            cursor = cursor.sort(*sort)

        result = []
        async for document in cursor:
            result.append(document)
        return json(result, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)


app.add_route(Search.as_view(), '/api/search')
