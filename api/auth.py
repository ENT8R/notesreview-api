import hashlib
import hmac
from functools import wraps

from sanic import Sanic
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


def hash_token(token):
    return hmac.new(
        config['TOKEN_SECRET'].encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


async def is_authenticated(request):
    if request.token is None:
        return False
    return (
        await Sanic.get_app().ctx.db.users.find_one(
            {'token': hash_token(request.token)}
        )
        is not None
    )


async def attach_uid(request):
    token = request.token
    # Fetch the uid with the token from the database and attach it
    # to the request context if a corresponding user exists
    if token is None:
        request.ctx.uid = None
    else:
        user = await Sanic.get_app().ctx.db.users.find_one(
            {'token': hash_token(request.token)}
        )
        request.ctx.uid = None if user is None else user['_id']
