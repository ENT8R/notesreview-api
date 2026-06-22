from typing import Any

import orjson
from pymongo.asynchronous.collection import AsyncCollection
from sanic import Blueprint, Sanic
from sanic.request import Request, RequestParameters
from sanic.response import JSONResponse, json

from api import docs
from config import Config
from search.filter import Filter
from search.limit import Limit
from search.sort import Sort

blueprint = Blueprint('Search', url_prefix='/search')
config = Config()


@blueprint.route('/', methods=['GET', 'POST'])
@docs.search
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

    await request.app.dispatch(
        'notesreview.request.search',
        context={
            'request': request,
            'args': args,
            'uid': uid,
            'sort': sort,
            'filter': filter,
            'limit': limit,
        },
    )

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
        .query(data.get('query'), data.get('scope'))
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
    limit = (
        Limit(data.get('limit'))
        .default(Sanic.get_app().config.DEFAULT_LIMIT)
        .max(Sanic.get_app().config.MAX_LIMIT)
        .build()
    )

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
) -> tuple[AsyncCollection, list[dict[str, Any]]]:
    # Default collection which will be used by nearly all queries
    collection: AsyncCollection = Sanic.get_app().ctx.db.notes

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

        pipelineHideWatchlist = [
            # Use a higher limit than allowed before the lookup operation
            # to limit the set of potential candidates for the exclusion check.
            # Do not use a hardcoded limit for this but instead calculate it from
            # the total (allowed) amount of notes on the watchlist of the current user and the actual limit
            {'$limit': Sanic.get_app().config.WATCHLIST_LIMIT + limit},
            *pipelineIncludeWatchlist,
            {
                '$match': {
                    'watchlist': {'$eq': None},
                },
            },
        ]

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
    collection: AsyncCollection, pipeline: list[dict[str, Any]]
) -> JSONResponse:
    cursor = await collection.aggregate(pipeline)
    result = []
    async for document in cursor:
        result.append(document)
    await cursor.close()
    return json(result, dumps=orjson.dumps, option=orjson.OPT_NAIVE_UTC)
