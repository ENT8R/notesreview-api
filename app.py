from textwrap import dedent

from jwt import PyJWKClient
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Blueprint, Sanic

from api.auth import attach_uid
from blueprints.auth import blueprint as auth
from blueprints.notes import blueprint as notes
from blueprints.search import blueprint as search
from blueprints.status import blueprint as status
from config import config

app = Sanic(__name__)
app.config.update(config)

app.ext.openapi.describe(
    'notesreview-api',
    version='0.1.0',
    description=dedent(
        """\
        # Information
        This API is still subject to change, especially the behavior of the `query` parameter might change in the future,
        because right now the possibilities are still a little bit limited.
        """
    ),
)
app.ext.openapi.add_security_scheme(
    'token',
    'http',
    scheme='bearer',
    bearer_format='JWT',
    description='OpenID Connect Token issued by OpenStreetMap',
)


@app.before_server_start
async def setup(app, loop):
    client = AsyncIOMotorClient(
        f'mongodb://{app.config.DB_USER}:{app.config.DB_PASSWORD}@{app.config.DB_HOST}:27017?authSource=notesreview',
        io_loop=loop,
    )
    jwks_client = PyJWKClient(app.config.OPENSTREETMAP_OAUTH_JWKS_URI)

    app.ctx.client = client
    app.ctx.db = client.notesreview
    app.ctx.jwks_client = jwks_client


@app.before_server_stop
async def shutdown(app, loop):
    app.ctx.client.close()


app.blueprint(Blueprint.group(auth, status, search, url_prefix='/api'))

app.register_middleware(attach_uid, 'request')
