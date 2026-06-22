from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar

from sanic.request import Request
from sanic.response import BaseHTTPResponse

Params = ParamSpec('Params')
ResponseType = TypeVar('ResponseType', bound=BaseHTTPResponse)
FunctionType = Callable[Concatenate[Request, Params], Awaitable[ResponseType]]
