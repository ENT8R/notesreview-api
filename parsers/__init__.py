from dataclasses import dataclass

from .query import Query
from .users import Users


@dataclass(frozen=True)
class Parsers:
    Query = Query()
    Users = Users()
