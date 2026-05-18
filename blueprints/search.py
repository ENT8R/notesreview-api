from textwrap import dedent
from typing import Any

import orjson
from motor.motor_asyncio import AsyncIOMotorCollection
from sanic import Blueprint, Sanic
from sanic.request import Request, RequestParameters
from sanic.response import JSONResponse, json
from sanic_ext import openapi

from api.models.note import Note
from api.query import Filter, Sort
from config import config

blueprint = Blueprint('Search', url_prefix='/search')


@blueprint.route('/', methods=['GET', 'POST'])
@openapi.summary('Search')
@openapi.description('Search and filter all notes in the database')
@openapi.parameter(
    'query',
    openapi.String(
        description=dedent(
            """\
            A word or sentence which can be found in the comments.
            To find an exact occurence of a word or sentence, wrap it in quotation marks `"{query}"`.
            Single words can be excluded from the result by prepending a dash `-` to the word.
            Spaces and other delimiters like dots are currently treated as a logical OR,
            though this will likely change in the future.
            """
        ),
        default=None,
        required=False,
    ),
)
@openapi.parameter(
    'bbox',
    openapi.String(
        description='A pair of coordinates specifying a rectangular box where all results are located in',
        example='-87.6955,41.8353,-87.5871,41.9170',
        default=None,
    ),
)
@openapi.parameter(
    'polygon',
    openapi.String(
        description='A GeoJSON polygon specifying a region where all results are located in',
        default=None,
    ),
)
@openapi.parameter(
    'status',
    openapi.String(
        description='The current status of the note',
        enum=('all', 'open', 'closed'),
        default='all',
    ),
)
@openapi.parameter(
    'anonymous',
    openapi.String(
        description='Whether anonymous notes should be included inclusively, excluded or included exclusively in the results',
        enum=('include', 'hide', 'only'),
        default='include',
    ),
)
@openapi.parameter(
    'author',
    openapi.String(
        description='Name of the user who opened the note, searching for multiple users is possible by separating them with a comma',
        default=None,
    ),
)
@openapi.parameter(
    'user',
    openapi.String(
        description='Name of any user who commented on the note, searching for multiple users is possible by separating them with a comma',
        default=None,
    ),
)
@openapi.parameter(
    'after',
    openapi.DateTime(
        description='Only return notes updated or created after this date',
        default=None,
        example='2020-03-13T10:20:24',
    ),
)
@openapi.parameter(
    'before',
    openapi.DateTime(
        description='Only return notes updated or created before this date',
        default=None,
        example='2020-05-11T07:10:45',
    ),
)
@openapi.parameter(
    'comments',
    openapi.Integer(
        description='Filters the amount of comments on a note',
        minimum=0,
        default=None,
    ),
)
@openapi.parameter(
    'commented',
    openapi.String(
        description='Whether commented notes should be included inclusively, excluded or included exclusively in the results',
        enum=('include', 'hide', 'only'),
        default='include',
    ),
)
@openapi.parameter(
    'watchlist',
    openapi.String(
        description='Whether notes on the watchlist should be included inclusively, excluded or included exclusively in the results',
        enum=('include', 'hide', 'only'),
        default='include',
    ),
)
@openapi.parameter(
    'sort_by',
    openapi.String(
        description='Sort notes either by no criteria, the date of the last update or their creation date',
        enum=('none', 'updated_at', 'created_at'),
        default='updated_at',
    ),
)
@openapi.parameter(
    'order',
    openapi.String(
        description='Sort notes either in ascending or descending order',
        enum=('descending', 'desc', 'ascending', 'asc'),
        default='descending',
    ),
)
@openapi.parameter(
    'limit',
    openapi.Integer(
        description='Limit the amount of notes to return',
        minimum=1,
        maximum=config['MAX_LIMIT'],
        default=config['DEFAULT_LIMIT'],
    ),
)
@openapi.response(
    200,
    {'application/json': openapi.Array(items=Note, uniqueItems=True)},
    'The response is an array containing the notes with the requested information',
)
@openapi.response(
    400,
    {
        'application/json': openapi.Object(
            properties={'error': openapi.String()}
        )
    },
    'In case one of the parameters is invalid, the response contains the error message',
)
async def index(request: Request) -> JSONResponse:
    try:
        args = {}
        if request.method == 'GET':
            args = request.args
        elif request.method == 'POST':
            args = request.json
        uid = request.ctx.uid if hasattr(request.ctx, 'uid') else None
        sort, filter, limit, watchlist = await parse(args, uid)
    except ValueError as error:
        return json({'error': str(error)}, status=400)

    collection, pipeline = build(sort, filter, limit, watchlist, uid)
    return await find(collection, pipeline)


async def parse(
    data: RequestParameters | dict[str, Any], uid: str | None
) -> tuple[tuple[str | None, int], dict[str, Any], int, str]:
    blocklist = None
    if uid is not None:
        blocklist = await Sanic.get_app().ctx.db.blocklist.distinct(
            'note', {'user': uid}
        )

    sort = (
        Sort()
        .by(data.get('sort_by'), 'updated_at')
        .order(data.get('order'), 'descending')
        .build()
    )
    filter = (
        Filter(sort)
        .exclude(blocklist)
        .query(data.get('query'))
        .bbox(data.get('bbox'))
        .polygon(data.get('polygon'))
        .status(data.get('status'))
        .anonymous(data.get('anonymous'))
        .author(data.get('author'))
        .user(data.get('user'))
        .after(data.get('after'))
        .before(data.get('before'))
        .comments(data.get('comments'))
        .commented(data.get('commented'))
        .build()
    )
    limit = data.get('limit', config['DEFAULT_LIMIT'])

    # Apply the default limit in case the argument could not be parsed (e.g. for limit=NaN)
    try:
        limit = int(limit)
    except ValueError:
        limit = config['DEFAULT_LIMIT']

    if limit > config['MAX_LIMIT']:
        return json(
            {'error': f'Limit must not be higher than {config["MAX_LIMIT"]}.'},
            status=400,
        )

    # Prevent that a limit of 0 is treated as no limit at all
    if limit == 0:
        limit = config['DEFAULT_LIMIT']

    # Determine how to handle entries on the watchlist in the final results
    watchlist = data.get('watchlist', 'include')
    if watchlist not in ['include', 'hide', 'only']:
        raise ValueError('Watchlist must be one of [include, hide, only]')

    # Do not allow watchlist queries except the default if the request is unauthenticated
    if uid is None and watchlist != 'include':
        raise ValueError(
            'Can not search user-specific watchlist if unauthenticated'
        )

    return sort, filter, limit, watchlist


# Define an aggregation pipeline to allow more complex queries than a call to find() can manage
def build(
    sort: tuple[str | None, int],
    filter: dict[str, Any],
    limit: int,
    watchlist: str,
    uid: int | None,
) -> tuple[AsyncIOMotorCollection, list[dict[str, Any]]]:
    # Default collection which will be used by nearly all queries
    collection: AsyncIOMotorCollection = Sanic.get_app().ctx.db.notes

    pipeline: list[dict[str, Any]] = [
        {'$match': filter},
    ]

    # Queries are faster if the sorting is not explicitly specified (if desired)
    if sort[0] is not None:
        pipeline.append({'$sort': {sort[0]: sort[1]}})

    # Apply the specified limit by adding a limit stage
    pipeline.append({'$limit': limit})

    # If the query is done by an authenticated user, allow for additional search options regarding the watchlist
    if uid is not None:
        pipelineIncludeWatchlist = [
            {
                '$lookup': {
                    'from': 'watchlist',
                    'let': {'id': '$_id'},
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': {
                                    '$and': [
                                        {'$eq': ['$note', '$$id']},
                                        {'$eq': ['$user', uid]},
                                    ]
                                }
                            }
                        },
                        {
                            '$project': {
                                '_id': 0,
                                'comment': 1,
                                'created_at': 1,
                                'updated_at': 1,
                            }
                        },
                    ],
                    'as': 'watchlist',
                }
            },
            {'$addFields': {'watchlist': {'$arrayElemAt': ['$watchlist', 0]}}},
        ]

        pipelineHideWatchlist = (
            [
                # Use a higher limit than allowed before the lookup operation
                # to limit the set of potential candidates for the exclusion check.
                # Do not use a hardcoded limit for this but instead calculate it from
                # the total (allowed) amount of notes on the watchlist of the current user and the actual limit
                {'$limit': config['WATCHLIST_LIMIT'] + limit},
            ]
            + pipelineIncludeWatchlist
            + [
                {
                    '$match': {
                        'watchlist': {'$eq': None},
                    },
                },
            ]
        )

        pipelineOnlyWatchlist = [
            {
                '$lookup': {
                    'from': 'notes',
                    'localField': 'note',
                    'foreignField': '_id',
                    'as': 'note',
                }
            },
            {'$unwind': '$note'},
            {
                '$replaceRoot': {
                    'newRoot': {
                        '$mergeObjects': [
                            '$note',
                            {
                                'watchlist': {
                                    'comment': '$comment',
                                    'created_at': '$created_at',
                                    'updated_at': '$updated_at',
                                },
                            },
                        ]
                    }
                }
            },
            {'$match': filter},
        ]

        if watchlist == 'include':
            # In the default case, only add a lookup pipeline at the end to include the information from the entries on the watchlist
            pipeline.extend(pipelineIncludeWatchlist)
        elif watchlist == 'hide':
            # Use a different pipeline to hide notes that are on the watchlist from the results
            pipeline[2:2] = pipelineHideWatchlist
        elif watchlist == 'only':
            # Use another pipeline to only show notes on the personal watchlist
            collection = Sanic.get_app().ctx.db.watchlist

            # Replace the original filter with a simple filter for the current uid,
            # because this search is performed against the watchlist collection,
            # however the original filter is still added at the end of this pipeline
            pipeline[0]['$match'] = {'user': uid}

            pipeline[1:1] = pipelineOnlyWatchlist

    return collection, pipeline


async def find(
    collection: AsyncIOMotorCollection, pipeline: list[dict[str, Any]]
) -> JSONResponse:
    cursor = collection.aggregate(pipeline)
    result = []
    async for document in cursor:
        result.append(document)
    return json(result, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)
