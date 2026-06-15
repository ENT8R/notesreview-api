import os
import re
from dataclasses import dataclass
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


class QueryInterpreter(lark.visitors.Interpreter):
    def __init__(self, scope: str) -> None:
        self.scope = scope

    # Build an $or combination of all children by visiting them
    def or_exp(self, tree: lark.Tree) -> dict[str, Any]:
        return {
            '$or': self.visit_children(tree),
        }

    # Build an $and combination of all children by visiting them
    def and_exp(self, tree: lark.Tree) -> dict[str, Any]:
        return {
            '$and': self.visit_children(tree),
        }

    # The child of a literal is an atomic expression or its negated form.
    # If nested expressions are allowed by the grammar, a literal can also have AND/OR
    # expressions as its child, otherwise only tokens or NOT expressions are possible
    def literal(self, tree: lark.Tree) -> dict[str, Any]:
        # Expect only a single child and raise an error if this is not the case
        if len(tree.children) != 1:
            raise ValueError('A literal can only have a single child')

        # If the child of this literal is a token, construct the expression of the term directly,
        # otherwise visit the child (i.e. in case of negations or nested expressions)
        if type(tree.children[0]) is lark.lexer.Token:
            return {
                self.scope: self._term(tree.children[0]),
            }
        else:
            return self.visit(tree.children[0])

    # Build a negated expression of the child by constructing the expression directly.
    # This works only if the child is a token or a token embedded in a literal.
    # If nested expressions are allowed by the grammar, a negated expression can also have
    # AND/OR expressions as its child, which will need to be visited as well
    def not_exp(self, tree: lark.Tree) -> dict[str, Any]:
        # Expect only a single child and raise an error if this is not the case
        if len(tree.children) != 1:
            raise ValueError(
                'A negated expression can only have a single child'
            )

        if type(tree.children[0]) is lark.lexer.Token:
            # NOT TERM
            return {
                self.scope: {
                    '$not': self._term(tree.children[0]),
                }
            }
        elif (
            tree.children[0].data == 'literal'
            and type(tree.children[0].children[0]) is lark.lexer.Token
        ):
            # NOT (TERM)
            return {
                self.scope: {
                    '$not': self._term(tree.children[0].children[0]),
                }
            }
        elif tree.children[0].data == 'or_exp':
            # NOT (and_exp OR and_exp)
            return {
                '$nor': self.visit_children(tree),
            }
        else:
            # NOT (literal AND literal)
            return {
                '$nor': [self.visit(tree.children[0])],
            }

    def _term(self, token: lark.lexer.Token) -> dict[str, str]:
        # Remove leading and trailing quotation marks from the string
        value = token.value
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Use a regex search in order to find the correct documents
        return {
            '$regex': (
                value.removeprefix('regex:')
                if value.startswith('regex:')
                else re.escape(value)
            ),
            '$options': 'i',
        }


class Query(object):
    def __init__(self) -> None:
        self.allowed_keywords = ('$and', '$or', '$nor')
        with open(
            os.path.join(os.path.dirname(__file__), 'grammars', 'query.lark')
        ) as file:
            self.grammar = lark.Lark(file.read())

    def parse(self, input: str | None, scope: str) -> dict[str, Any]:
        if input is not None:
            try:
                tree = self.grammar.parse(input)
                return QueryInterpreter(scope).visit(tree)
            except lark.exceptions.UnexpectedInput as error:
                raise ValueError(str(error) + error.get_context(input))
        return {}


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


@dataclass(frozen=True)
class Parsers:
    Users = Users()
    Query = Query()
