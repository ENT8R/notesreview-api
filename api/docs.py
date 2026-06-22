from collections.abc import Callable
from textwrap import dedent

from sanic_ext import openapi

from config import Config
from models.note import Note

from . import types

config = Config()


# fmt: off
def compose(*decorators: Callable[[types.FunctionType], types.FunctionType]) -> Callable[[types.FunctionType], types.FunctionType]:
    # fmt: on
    def wrapper(f: types.FunctionType) -> types.FunctionType:
        for decorator in decorators:
            f = decorator(f)
        return f

    return wrapper


search = compose(
    openapi.summary('Search'),
    openapi.description('Search and filter all notes in the database'),
    openapi.parameter(
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
    ),
    openapi.parameter(
        'scope',
        openapi.String(
            description='Where to search for the string specified in the query, this can be either all comments of a note or just the initial comment',
            enum=('all', 'first'),
            default='first',
        ),
    ),
    openapi.parameter(
        'bbox',
        openapi.String(
            description='A pair of coordinates specifying a rectangular box where all results are located in',
            example='-87.6955,41.8353,-87.5871,41.9170',
            default=None,
        ),
    ),
    openapi.parameter(
        'polygon',
        openapi.String(
            description='A GeoJSON polygon specifying a region where all results are located in',
            default=None,
        ),
    ),
    openapi.parameter(
        'status',
        openapi.String(
            description='The current status of the note',
            enum=('all', 'open', 'closed'),
            default='all',
        ),
    ),
    openapi.parameter(
        'anonymous',
        openapi.String(
            description='Whether anonymous notes should be included inclusively, excluded or included exclusively in the results',
            enum=('include', 'hide', 'only'),
            default='include',
        ),
    ),
    openapi.parameter(
        'author',
        openapi.String(
            description='Name of the user who opened the note, searching for multiple users is possible by separating them with a comma',
            default=None,
        ),
    ),
    openapi.parameter(
        'user',
        openapi.String(
            description='Name of any user who commented on the note, searching for multiple users is possible by separating them with a comma',
            default=None,
        ),
    ),
    openapi.parameter(
        'after',
        openapi.DateTime(
            description='Only return notes updated or created after this date',
            default=None,
            example='2020-03-13T10:20:24',
        ),
    ),
    openapi.parameter(
        'before',
        openapi.DateTime(
            description='Only return notes updated or created before this date',
            default=None,
            example='2020-05-11T07:10:45',
        ),
    ),
    openapi.parameter(
        'comments',
        openapi.Integer(
            description='Filters the amount of comments on a note',
            minimum=0,
            default=None,
        ),
    ),
    openapi.parameter(
        'commented',
        openapi.String(
            description='Whether commented notes should be included inclusively, excluded or included exclusively in the results',
            enum=('include', 'hide', 'only'),
            default='include',
        ),
    ),
    openapi.parameter(
        'watchlist',
        openapi.String(
            description='Whether notes on the watchlist should be included inclusively, excluded or included exclusively in the results',
            enum=('include', 'hide', 'only'),
            default='include',
        ),
    ),
    openapi.parameter(
        'sort_by',
        openapi.String(
            description='Sort notes either by no criteria, the date of the last update or their creation date',
            enum=('none', 'updated_at', 'created_at'),
            default='updated_at',
        ),
    ),
    openapi.parameter(
        'order',
        openapi.String(
            description='Sort notes either in ascending or descending order',
            enum=('descending', 'desc', 'ascending', 'asc'),
            default='descending',
        ),
    ),
    openapi.parameter(
        'limit',
        openapi.Integer(
            description='Limit the amount of notes to return',
            minimum=1,
            maximum=config.MAX_LIMIT,
            default=config.DEFAULT_LIMIT,
        ),
    ),
    openapi.response(
        200,
        {'application/json': openapi.Array(items=Note, uniqueItems=True)},
        'The response is an array containing the notes with the requested information',
    ),
    openapi.response(
        400,
        {
            'application/json': openapi.Object(
                properties={'error': openapi.String()}
            )
        },
        'In case one of the parameters is invalid, the response contains the error message',
    ),
)
