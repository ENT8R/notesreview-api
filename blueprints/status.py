import os

from sanic import Blueprint, Sanic
from sanic.request import Request
from sanic.response import JSONResponse, json
from sanic_ext import openapi

blueprint = Blueprint('Status', url_prefix='/status')


@blueprint.route('/')
@openapi.summary('Status')
@openapi.description(
    'Status information about the database and update frequency'
)
@openapi.response(
    200,
    {
        'application/json': openapi.Object(
            properties={
                'last_import': openapi.DateTime(),
                'last_sync': openapi.DateTime(),
                'last_update': openapi.DateTime(),
            }
        ),
    },
    'The response is an object with the currently available status information',
)
async def status(request: Request) -> JSONResponse:
    last_import = None
    last_sync = None
    last_update = None

    root = Sanic.get_app().config.ROOT_PATH
    with (
        open(os.path.join(root, 'scripts', 'LAST_IMPORT.txt')) as file1,
        open(os.path.join(root, 'scripts', 'LAST_SYNC.txt')) as file2,
        open(os.path.join(root, 'scripts', 'LAST_UPDATE.txt')) as file3,
    ):
        last_import = file1.read().strip()
        last_sync = file2.read().strip()
        last_update = file3.read().strip()

    return json(
        {
            'last_import': last_import,
            'last_sync': last_sync,
            'last_update': last_update,
        }
    )
