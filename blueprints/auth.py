import datetime

import jwt
from sanic import Blueprint, Sanic
from sanic.response import text
from sanic_ext import openapi

from api.auth import decode_token, protected

blueprint = Blueprint('Authentication', url_prefix='/auth')


@blueprint.get('/login')
@openapi.description('Login with a valid OpenID Connect Token (JWT)')
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
async def login(request):
    token = request.token
    info = None

    if token is None:
        return text('No token provided', 401)

    try:
        info = decode_token(token)
    except jwt.exceptions.InvalidTokenError:
        return text('The provided token is invalid', 401)

    # Do not proceed if the token does not contain the required information
    if info is None or 'sub' not in info or 'preferred_username' not in info:
        return text(
            'The provided token can not be used for authentication', 401
        )

    # Store or update the token and the user id in the database
    uid = int(info['sub'])
    username = info['preferred_username']
    timestamp = datetime.datetime.now(datetime.timezone.utc)

    await Sanic.get_app().ctx.db.users.update_one(
        {
            '_id': uid,
        },
        {
            '$setOnInsert': {
                '_id': uid,
                'created_at': timestamp,
            },
            '$set': {
                'token': token,
                'user': username,
                'last_validated_at': timestamp,
            },
        },
        upsert=True,
    )

    return text('OK', 200)


@blueprint.get('/logout')
@openapi.description('Logout with a valid OpenID Connect Token (JWT)')
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
