import os
import re
from typing import Any, Self

import dateutil.parser
import lark
import orjson


class Sort(object):
    def build(self) -> tuple[str | None, int]:
        return self._by, self._order

    def by(self, by: str | None, default: str) -> Self:
        if by is None:
            by = default

        allowed = ['none', 'updated_at', 'created_at']
        if by not in allowed:
            raise ValueError(f'Sort must be one of {allowed}')

        if by == 'none':
            self._by = None
        elif by == 'updated_at':
            self._by = 'updated_at'
        elif by == 'created_at':
            self._by = 'comments.0.date'
        return self

    def order(self, order: str | None, default: str) -> Self:
        if order is None:
            order = default

        allowed = ['desc', 'descending', 'asc', 'ascending']
        if order not in allowed:
            raise ValueError(f'Order must be one of {allowed}')

        if order in ['asc', 'ascending']:
            self._order = 1
        elif order in ['desc', 'descending']:
            self._order = -1
        return self


class Filter(object):
    def __init__(self, sort: tuple[str | None, int]) -> None:
        self.filter = {}
        self.sort = sort
        self.users = Users()

    def build(self) -> dict[str, Any]:
        return self.filter

    def exclude(self, blocklist: list[int] | None) -> Self:
        if blocklist is not None and len(blocklist) > 0:
            self.filter['_id'] = {'$nin': blocklist}
        return self

    def query(self, query: str | None) -> Self:
        if query is not None:
            self.filter['comments.0.text'] = {
                '$regex': (
                    query.removeprefix('regex:')
                    if query.startswith('regex:')
                    else re.escape(query)
                ),
                '$options': 'i',
            }
        return self

    def bbox(self, input: str | None) -> Self:
        if input is not None:
            bbox = BoundingBox(input)
            self.filter['coordinates'] = {
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
            self.filter['coordinates'] = {
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
            self.filter['status'] = status
        return self

    def anonymous(self, anonymous: str | None) -> Self:
        if anonymous not in [None, 'include', 'hide', 'only']:
            raise ValueError('Anonymous must be one of [include, hide, only]')

        if anonymous is not None:
            # Filtering out anonymous notes means that there must be a user who created the note
            if anonymous == 'hide':
                self.filter['comments.0.user'] = {'$exists': True}
            if anonymous == 'only':
                self.filter['comments.0.user'] = {'$exists': False}
        return self

    def author(self, author: str | None) -> Self:
        if author is not None:
            include, exclude = self.users.parse(author)
            if 'comments.0.user' not in self.filter:
                self.filter['comments.0.user'] = {}
            self.filter['comments.0.user'].update(
                self.clean({'$in': include, '$nin': exclude})
            )
        return self

    def user(self, user: str | None) -> Self:
        if user is not None:
            include, exclude = self.users.parse(user)
            if 'comments.user' not in self.filter:
                self.filter['comments.user'] = {}
            self.filter['comments.user'].update(
                self.clean({'$all': include, '$nin': exclude})
            )
        return self

    def after(self, after: str | None) -> Self:
        if after is not None:
            key = self.sort[0]
            # If results will be unsorted, use the creation date for the comparison
            if key is None:
                key = 'comments.0.date'

            if key not in self.filter:
                self.filter[key] = {}
            self.filter[key]['$gt'] = dateutil.parser.parse(after)
        return self

    def before(self, before: str | None) -> Self:
        if before is not None:
            key = self.sort[0]
            # If results will be unsorted, use the creation date for the comparison
            if key is None:
                key = 'comments.0.date'

            if key not in self.filter:
                self.filter[key] = {}
            self.filter[key]['$lt'] = dateutil.parser.parse(before)
        return self

    def comments(self, amount_of_comments: str | None) -> Self:
        if amount_of_comments is not None:
            # A comment of the note counts as everything after the original comment
            self.filter['comments'] = {'$size': int(amount_of_comments) + 1}
        return self

    def commented(self, commented: str | None) -> Self:
        if commented not in [None, 'include', 'hide', 'only']:
            raise ValueError('Commented must be one of [include, hide, only]')

        if commented is not None:
            # Filtering out commented notes means that only the original comment exists
            if commented == 'hide':
                self.filter['comments'] = {'$size': 1}
            # Showing only commented notes requires the amount of comments to be greater than 1
            # This is not directly allowed (since $size does not accept ranges of values, e.g. via $gt),
            # so instead show only notes with an amount of comments different from 1
            # (notes with 0 comments do not exist)
            if commented == 'only':
                self.filter['comments'] = {'$not': {'$size': 1}}
        return self

    # Remove values that are not defined or empty from a given dictionary
    def clean(self, dictionary: dict) -> dict:
        return {
            k: v
            for k, v in dictionary.items()
            if v is not None and (type(v) is list and len(v) > 0)
        }


class Limit(object):
    def __init__(self, input: str | None) -> None:
        self.input = input

    def default(self, default: int) -> Self:
        self._default = default
        return self

    def max(self, max: int) -> Self:
        self._max = max
        return self

    def build(self) -> int:
        if self._default is None:
            raise ValueError(
                'Set a default limit by calling default() before calling build()'
            )

        if self._max is None:
            raise ValueError(
                'Set a maximum limit by calling max() before calling build()'
            )

        if self.input is None:
            return self._default

        # Apply the default limit in case the argument could not be parsed (e.g. for limit=NaN)
        try:
            limit = int(self.input) if self.input else self._default
        except ValueError:
            limit = self._default

        if limit > self._max:
            raise ValueError(f'Limit must not be higher than {self._max}.')

        # Prevent that a limit of 0 is treated as no limit at all
        if limit == 0:
            limit = self._default

        return limit


class BoundingBox(object):
    def __init__(self, input: str) -> None:
        bbox = [float(x) for x in input.split(',')]
        if len(bbox) != 4:
            raise ValueError(
                'The bounding box does not contain all required coordinates'
            )

        self.x1 = bbox[0]
        self.y1 = bbox[1]
        self.x2 = bbox[2]
        self.y2 = bbox[3]
        self.check()

    def check(self) -> None:
        if self.x1 > self.x2:
            raise ValueError(
                'The minimum longitude must be smaller than the maximum longitude'
            )
        if self.y1 > self.y2:
            raise ValueError(
                'The minimum latitude must be smaller than the maximum latitude'
            )
        if self.x1 < -180 or self.y1 < -90 or self.x2 > +180 or self.y2 > +90:
            raise ValueError(
                'The bounding box exceeds the size of the world, please specify a smaller bounding box'
            )


class Polygon(object):
    def __init__(self, polygon: str) -> None:
        polygon = orjson.loads(polygon)
        if 'type' not in polygon or 'coordinates' not in polygon:
            raise ValueError(
                'Polygon does not contain information about type or any coordinates'
            )

        self.type = polygon['type']
        self.coordinates = polygon['coordinates']
        self.check()

    def check(self) -> None:
        if self.type not in ['Polygon', 'MultiPolygon']:
            raise ValueError(
                'The GeoJSON shape must be either a Polygon or a MultiPolygon'
            )
        if type(self.coordinates) is not list:
            raise ValueError('Coordinates have to be supplied as an array')


class Users(object):
    def __init__(self) -> None:
        with open(
            os.path.join(os.path.dirname(__file__), 'grammars', 'users.lark')
        ) as file:
            self.grammar = lark.Lark(file.read())

    def parse(self, input: str) -> tuple[list[Any], list[Any]]:
        tree = self.grammar.parse(input)
        include = []
        exclude = []

        for node in tree.children:
            if not isinstance(node, lark.Tree):
                continue
            expression = node.children[0]
            if isinstance(expression, lark.Token):
                include.append(expression.value)
            elif (
                isinstance(expression, lark.Tree) and expression.data == 'not'
            ):
                exclude.append(expression.children[0])

        if len(include) + len(exclude) > 10:
            raise ValueError(
                'The amount of users to search for exceeds the limit'
            )

        return include, exclude
