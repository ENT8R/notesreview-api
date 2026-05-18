import datetime

import orjson
from sanic import Blueprint, Sanic
from sanic.request import Request
from sanic.response import HTTPResponse, JSONResponse, json, text
from sanic_ext import openapi

from api.auth import protected
from config import config

blueprint = Blueprint('Watchlist', url_prefix='/watchlist')


@blueprint.post(r'/<id:\d+>')
@openapi.summary('Watch')
@openapi.description('Add a note to the personal watchlist')
@openapi.secured('token')
@openapi.parameter(
    'id',
    openapi.Integer(
        description='ID of the note to add to the watchlist',
    ),
    'path',
)
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@openapi.response(
    403,
    {
        'text/plain': openapi.String(),
    },
    'Note can not be added to the watchlist because it would exceed the limit',
)
@protected
async def watch(request: Request, id: int) -> HTTPResponse:
    # Apply a limit for the maximum number of notes that a user can add to his watchlist
    documents = await Sanic.get_app().ctx.db.watchlist.count_documents(
        {
            'user': request.ctx.uid,
        }
    )
    if documents >= config['WATCHLIST_LIMIT']:
        return text(
            f'Can not add note to watchlist, current limit is at {config["WATCHLIST_LIMIT"]}',
            403,
        )

    # Upsert a watchlist entry for the current user and specified note with the current timestamp
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    comment = request.json.get('comment') if request.json else None
    await Sanic.get_app().ctx.db.watchlist.update_one(
        {
            'note': int(id),
            'user': request.ctx.uid,
        },
        {
            '$setOnInsert': {
                'note': int(id),
                'user': request.ctx.uid,
                'created_at': timestamp,
            },
            '$set': {
                'updated_at': timestamp,
                'comment': comment,
            },
        },
        upsert=True,
    )
    return text('OK', 200)


@blueprint.delete(r'/<id:\d+>')
@openapi.summary('Unwatch')
@openapi.description('Remove a note from the personal watchlist')
@openapi.secured('token')
@openapi.parameter(
    'id',
    openapi.Integer(
        description='ID of the note to remove from the watchlist',
    ),
    'path',
)
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@protected
async def unwatch(request: Request, id: int) -> HTTPResponse:
    # Remove the watchlist entry for the current user and specified note
    await Sanic.get_app().ctx.db.watchlist.delete_one(
        {
            'note': int(id),
            'user': request.ctx.uid,
        }
    )
    return text('OK', 200)


@blueprint.get('/')
@openapi.summary('Watchlist')
@openapi.description('Get all entries of the personal watchlist')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'application/json': openapi.Array(
            items=openapi.Object(
                properties={
                    'note': openapi.String(),
                    'created_at': openapi.DateTime(),
                    'updated_at': openapi.DateTime(),
                    'comment': openapi.String(),
                }
            ),
            uniqueItems=True,
        )
    },
    'OK',
)
@protected
async def watchlist(request: Request) -> JSONResponse:
    # List all notes on the watchlist for the current user
    cursor = Sanic.get_app().ctx.db.watchlist.find(
        {
            'user': request.ctx.uid,
        },
        {
            '_id': False,
            'note': True,
            'created_at': True,
            'updated_at': True,
            'comment': True,
        },
    )
    result = []
    async for document in cursor:
        result.append(document)
    return json(result, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)


@blueprint.delete('/')
@openapi.summary('Delete watchlist')
@openapi.description('Delete all entries of the personal watchlist')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@protected
async def delete_watchlist(request: Request) -> HTTPResponse:
    # Remove all watchlist entries for the current user
    await Sanic.get_app().ctx.db.watchlist.delete_many(
        {
            'user': request.ctx.uid,
        }
    )
    return text('OK', 200)
