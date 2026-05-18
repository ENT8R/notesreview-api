import datetime

import orjson
from sanic import Blueprint, Sanic
from sanic.response import json, text
from sanic_ext import openapi

from api.auth import protected
from config import config

blueprint = Blueprint('Blocklist', url_prefix='/blocklist')


@blueprint.post(r'/<id:\d+>')
@openapi.summary('Hide')
@openapi.description('Hide a note from all search results')
@openapi.secured('token')
@openapi.parameter(
    'id',
    openapi.Integer(
        description='ID of the note to add to the blocklist',
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
    'Note can not be added to the blocklist because it would exceed the limit',
)
@protected
async def hide(request, id):
    # Apply a limit for the maximum number of notes that a user can add to his watchlist
    documents = await Sanic.get_app().ctx.db.blocklist.count_documents(
        {
            'user': request.ctx.uid,
        }
    )
    if documents >= config['BLOCKLIST_LIMIT']:
        return text(
            f'Can not add note to blocklist, current limit is at {config["BLOCKLIST_LIMIT"]}',
            403,
        )

    # Upsert a blocklist entry for the current user and specified note with the current timestamp
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    await Sanic.get_app().ctx.db.blocklist.update_one(
        {
            'note': int(id),
            'user': request.ctx.uid,
        },
        {
            '$setOnInsert': {
                'note': int(id),
                'user': request.ctx.uid,
            },
            '$set': {
                'hidden_at': timestamp,
            },
        },
        upsert=True,
    )
    return text('OK', 200)


@blueprint.delete(r'/<id:\d+>')
@openapi.summary('Unhide')
@openapi.description('Remove a note from the personal blocklist')
@openapi.secured('token')
@openapi.parameter(
    'id',
    openapi.Integer(
        description='ID of the note to remove from the blocklist',
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
async def unhide(request, id):
    # Remove the blocklist entry for the current user and specified note
    await Sanic.get_app().ctx.db.blocklist.delete_one(
        {
            'note': int(id),
            'user': request.ctx.uid,
        }
    )
    return text('OK', 200)


@blueprint.get('/')
@openapi.summary('Blocklist')
@openapi.description('Get all entries of the personal blocklist')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'application/json': openapi.Array(
            items=openapi.Integer(description='ID of the notes'),
            uniqueItems=True,
        )
    },
    'OK',
)
@protected
async def blocklist(request):
    # List all hidden notes for the current user
    uid = request.ctx.uid
    ids = await Sanic.get_app().ctx.db.blocklist.distinct(
        'note', {'user': uid}
    )
    return json(ids, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)


@blueprint.delete('/')
@openapi.summary('Delete blocklist')
@openapi.description('Delete all entries of the personal blocklist')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@protected
async def delete_blocklist(request):
    # Remove all blocklist entries for the current user
    await Sanic.get_app().ctx.db.blocklist.delete_many(
        {
            'user': request.ctx.uid,
        }
    )
    return text('OK', 200)
