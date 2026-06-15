from typing import Any, Self

import dateutil.parser

from parsers import Parsers

from .bbox import BoundingBox
from .polygon import Polygon


class Filter(object):
    def __init__(self, sort: tuple[str | None, int]) -> None:
        self._filter = {}
        self._query = {}
        self.sort = sort

    def build(self) -> dict[str, Any]:
        # If the query is empty or contains just a single word/term without any of the allowed keywords in it,
        # add the query for this term to the filter and return it directly without any other transformations
        if len(self._query) == 0 or all(
            k not in self._query for k in Parsers.Query.allowed_keywords
        ):
            self._filter.update(self._query)
            return self._filter

        # If the filter (for all other inputs except the query) is empty, the query can be used directly
        # as the filter instead without constructing the superfluous $and array in the next step
        if len(self._filter) == 0:
            return self._query

        if len(self._query) > 1:
            # This error should never be raised, this is just there in case something goes wrong during the parsing
            raise ValueError('Query has more than a single root node')

        # Transform all other filter arguments (without the query) to a global $and operator,
        # the resulting filter is then extended in the next step with the query information
        result = {
            '$and': [{k: v} for k, v in self._filter.items()],
        }

        if '$and' in self._query:
            # If the query is an $and combination as well, concatenate its elements with the global $and filter
            # https://www.mongodb.com/docs/manual/reference/operator/query/and/
            result['$and'] += self._query['$and']
        elif '$or' in self._query or '$nor' in self._query:
            # If the query is either a $or or a $nor, append it as a single element to the global $and filter
            # https://www.mongodb.com/docs/manual/reference/operator/query/or/
            # https://www.mongodb.com/docs/manual/reference/operator/query/nor/
            result['$and'].append(self._query)
        else:
            # This error should never be raised, this is just there in case something goes wrong
            raise ValueError(
                'Encountered unexpected keyword in query: '
                + list(self._query.keys())[0]
            )

        return result

    def exclude(self, blocklist: list[int] | None) -> Self:
        if blocklist is not None and len(blocklist) > 0:
            self._filter['_id'] = {'$nin': blocklist}
        return self

    def query(self, query: str | None, scope: str | None) -> Self:
        if query is not None:
            # Allow searching for the query string in all comments, not just the first ones of each note
            if scope not in [None, 'all', 'first']:
                raise ValueError('Scope must be one of [all, first]')
            scope = 'comments.text' if scope == 'all' else 'comments.0.text'
            self._query = Parsers.Query.parse(query, scope)
        return self

    def bbox(self, input: str | None) -> Self:
        if input is not None:
            bbox = BoundingBox(input)
            self._filter['coordinates'] = {
                '$geoWithin': {
                    '$box': [
                        # bottom left coordinates (longitude, latitude)
                        [bbox.x1, bbox.y1],
                        # upper right coordinates (longitude, latitude)
                        [bbox.x2, bbox.y2],
                    ]
                }
            }
        return self

    def polygon(self, input: str | None) -> Self:
        if input is not None:
            polygon = Polygon(input)
            self._filter['coordinates'] = {
                '$geoWithin': {
                    '$geometry': {
                        'type': polygon.type,
                        'coordinates': polygon.coordinates,
                    }
                }
            }
        return self

    def status(self, status: str | None) -> Self:
        if status not in [None, 'all', 'open', 'closed']:
            raise ValueError('Status must be one of [all, open, closed]')

        if status not in [None, 'all']:
            self._filter['status'] = status
        return self

    def anonymous(self, anonymous: str | None) -> Self:
        if anonymous not in [None, 'include', 'hide', 'only']:
            raise ValueError('Anonymous must be one of [include, hide, only]')

        if anonymous is not None:
            # Filtering out anonymous notes means that there must be a user who created the note
            if anonymous == 'hide':
                self._filter['comments.0.user'] = {'$exists': True}
            if anonymous == 'only':
                self._filter['comments.0.user'] = {'$exists': False}
        return self

    def author(self, author: str | None) -> Self:
        if author is not None:
            include, exclude = Parsers.Users.parse(author)
            if 'comments.0.user' not in self._filter:
                self._filter['comments.0.user'] = {}
            self._filter['comments.0.user'].update(
                self.clean({'$in': include, '$nin': exclude})
            )
        return self

    def user(self, user: str | None) -> Self:
        if user is not None:
            include, exclude = Parsers.Users.parse(user)
            if 'comments.user' not in self._filter:
                self._filter['comments.user'] = {}
            self._filter['comments.user'].update(
                self.clean({'$all': include, '$nin': exclude})
            )
        return self

    def after(self, after: str | None) -> Self:
        if after is not None:
            key = self.sort[0]
            # If results will be unsorted, use the creation date for the comparison
            if key is None:
                key = 'comments.0.date'

            if key not in self._filter:
                self._filter[key] = {}
            self._filter[key]['$gt'] = dateutil.parser.parse(after)
        return self

    def before(self, before: str | None) -> Self:
        if before is not None:
            key = self.sort[0]
            # If results will be unsorted, use the creation date for the comparison
            if key is None:
                key = 'comments.0.date'

            if key not in self._filter:
                self._filter[key] = {}
            self._filter[key]['$lt'] = dateutil.parser.parse(before)
        return self

    def comments(self, amount_of_comments: str | None) -> Self:
        if amount_of_comments is not None:
            # A comment of the note counts as everything after the original comment
            self._filter['comments'] = {'$size': int(amount_of_comments) + 1}
        return self

    def commented(self, commented: str | None) -> Self:
        if commented not in [None, 'include', 'hide', 'only']:
            raise ValueError('Commented must be one of [include, hide, only]')

        if commented is not None:
            # Filtering out commented notes means that only the original comment exists
            if commented == 'hide':
                self._filter['comments'] = {'$size': 1}
            # Showing only commented notes requires the amount of comments to be greater than 1
            # This is not directly allowed (since $size does not accept ranges of values, e.g. via $gt),
            # so instead show only notes with an amount of comments different from 1
            # (notes with 0 comments do not exist)
            if commented == 'only':
                self._filter['comments'] = {'$not': {'$size': 1}}
        return self

    # Remove values that are not defined or empty from a given dictionary
    def clean(self, dictionary: dict) -> dict:
        return {
            k: v
            for k, v in dictionary.items()
            if v is not None and (type(v) is list and len(v) > 0)
        }
