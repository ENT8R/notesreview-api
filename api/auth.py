from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

import jwt
from sanic import Sanic
from sanic.exceptions import Unauthorized
from sanic.request import Request
from sanic.response import BaseHTTPResponse

Params = ParamSpec('Params')
ResponseType = TypeVar('ResponseType', bound=BaseHTTPResponse)


# fmt: off
def protected(wrapped: Callable[Concatenate[Request, Params], Awaitable[ResponseType]]) -> Callable[Concatenate[Request, Params], Awaitable[ResponseType]]:
    def decorator(f: Callable[Concatenate[Request, Params], Awaitable[ResponseType]]) -> Callable[Concatenate[Request, Params], Awaitable[ResponseType]]:
        @wraps(f)
        async def decorated_function(request: Request, *args: Params.args, **kwargs: Params.kwargs) -> ResponseType:
            # fmt: on
            # Call the request handler only if there is a known uid for the
            # token which is already attached to the request context through
            # the middleware below before every request
            if request.ctx.uid is None:
                raise Unauthorized('You are unauthorized')
            else:
                response = await f(request, *args, **kwargs)
                return response

        return decorated_function

    return decorator(wrapped)


def decode_token(token: str) -> dict:
    signing_key = Sanic.get_app().ctx.jwks_client.get_signing_key_from_jwt(
        token
    )
    return jwt.decode(
        token,
        signing_key,
        audience=Sanic.get_app().config.OPENSTREETMAP_OAUTH_CLIENT_ID,
        options={'verify_exp': False},
        algorithms=['RS256'],
    )


async def is_authenticated(request: Request) -> bool:
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


async def attach_uid(request: Request) -> None:
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
