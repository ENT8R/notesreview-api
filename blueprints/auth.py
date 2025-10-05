import datetime

import httpx
from sanic import Blueprint, Sanic
from sanic.response import text
from sanic_ext import openapi

from api.auth import hash_token, protected

blueprint = Blueprint('Authentication', url_prefix='/auth')


@blueprint.get('/login')
@openapi.description('Login with a valid OAuth2 token')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@openapi.response(
    401,
    {
        'text/plain': openapi.String(),
    },
    'Invalid token or unauthorized',
)
@openapi.response(
    503,
    {
        'text/plain': openapi.String(),
    },
    'Could not connect to the OpenStreetMap API',
)
async def login(request):
    token = request.token
    info = None

    if token is None:
        return text('No token provided', 401)

    async with httpx.AsyncClient() as client:
        # Use the OpenStreetMap API to verify the token and get the corresponding user info
        try:
            r = await client.get(
                'https://www.openstreetmap.org/oauth2/userinfo',
                headers={'Authorization': f'Bearer {token}'},
            )
            if r.status_code != 200:
                return text('The provided token is invalid', 401)
            info = r.json()
        except httpx.RequestError:
            return text(
                'Could not connect to the OpenStreetMap API for verifying the token',
                503,
            )

    if info is None or 'sub' not in info:
        return text(
            'The provided token can not be used for authentication', 401
        )

    # Store or update the token hash and the user id in the database
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    await Sanic.get_app().ctx.db.users.update_one(
        {
            '_id': int(info['sub']),
        },
        {
            '$setOnInsert': {
                '_id': int(info['sub']),
                'created_at': timestamp,
            },
            '$set': {
                'token': hash_token(token),
                'user': info['preferred_username'],
                'last_validated_at': timestamp,
            },
        },
        upsert=True,
    )

    return text('OK', 200)


@blueprint.get('/logout')
@openapi.description('Logout with a valid OAuth2 token')
@openapi.secured('token')
@openapi.response(
    200,
    {
        'text/plain': openapi.String(),
    },
    'OK',
)
@protected
async def logout(request):
    await Sanic.get_app().ctx.db.users.update_one(
        {
            '_id': request.ctx.uid,
        },
        {'$set': {'token': None}},
    )
    return text('OK', 200)
