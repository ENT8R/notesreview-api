from functools import wraps

import jwt
from sanic import HTTPResponse, Sanic
from sanic.request import Request
from sanic.response import text

from config import config


def protected(wrapped):
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            # Call the request handler only if there is a known uid for the
            # token which is already attached to the request context through
            # the middleware below before every request
            if request.ctx.uid is None:
                return text('You are unauthorized', 401)
            else:
                response = await f(request, *args, **kwargs)
                return response

        return decorated_function

    return decorator(wrapped)


def decode_token(token):
    signing_key = Sanic.get_app().ctx.jwks_client.get_signing_key_from_jwt(
        token
    )
    return jwt.decode(
        token,
        signing_key,
        audience=config['OPENSTREETMAP_OAUTH_CLIENT_ID'],
        options={'verify_exp': False},
        algorithms=['RS256'],
    )


async def is_authenticated(request):
    token = request.token
    if token is None:
        return False

    info = None
    try:
        info = decode_token(token)
    except jwt.exceptions.InvalidTokenError:
        return False

    if info is None or 'sub' not in info:
        return False

    return (
        await Sanic.get_app().ctx.db.users.find_one({'_id': int(info['sub'])})
        is not None
    )


async def attach_uid(request):
    request.ctx.uid = None

    token = request.token
    if token is None:
        return

    # Validate the JWT and extract the user id (sub claim)
    info = None
    try:
        info = decode_token(token)
    except jwt.exceptions.InvalidTokenError:
        return

    # Do not attach a uid if there is no information after decoding the token
    if info is None or 'sub' not in info:
        return

    # Check if the user exists (logged in before) and is currently using this token
    uid = int(info['sub'])
    user = await Sanic.get_app().ctx.db.users.find_one({'_id': uid})
    if user is None or user['token'] != token:
        return

    # Finally attach the uid to the request context
    request.ctx.uid = uid
