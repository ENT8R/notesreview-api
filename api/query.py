import re

import dateutil.parser


class Sort(object):
    def __init__(self):
        self.sort = {}

    def build(self):
        return self.sort['by'], self.sort['order']

    def by(self, by):
        allowed = ['updated_at', 'created_at']
        if by not in allowed:
            raise ValueError(f'Sort must be one of {allowed}')

        self.sort['by'] = 'comments.0.date' if by == 'created_at' else 'updated_at'
        return self

    def order(self, order):
        allowed = ['desc', 'descending', 'asc', 'ascending']
        if order not in allowed:
            raise ValueError(f'Order must be one of {allowed}')

        self.sort['order'] = 1 if order in ['asc', 'ascending'] else -1
        return self


class Filter(object):
    def __init__(self, sort):
        self.filter = {}
        self.sort = sort

    def build(self):
        return self.filter

    def query(self, query):
        if query is not None:
            self.filter['comments.0.text'] = {
                '$regex': query[len('regex:'):] if query.startswith('regex:') else re.escape(query),
                '$options': 'i'
            }
        return self

    def bbox(self, bbox):
        if bbox is not None:
            bbox = BoundingBox(bbox)
            self.filter['coordinates'] = {
                '$geoWithin': {
                    '$box':  [
                        # bottom left coordinates (longitude, latitude)
                        [bbox.x1, bbox.y1],
                        # upper right coordinates (longitude, latitude)
                        [bbox.x2, bbox.y2]
                    ]
                }
            }
        return self

    def status(self, status):
        if status not in [None, 'all', 'open', 'closed']:
            raise ValueError('Status must be one of [all, open, closed]')

        if status not in [None, 'all']:
            self.filter['status'] = status
        return self

    def anonymous(self, anonymous):
        if anonymous not in [None, 'include', 'hide', 'only']:
            raise ValueError('Anonymous must be one of [include, hide, only]')

        if anonymous is not None:
            # Filtering out anonymous notes means that there must be a user who created the note
            if anonymous == 'hide':
                self.filter['comments.0.user'] = {
                    '$exists': True
                }
            if anonymous == 'only':
                self.filter['comments.0.user'] = {
                    '$exists': False
                }
        return self

    def author(self, author):
        if author is not None:
            self.filter['comments.0.user'] = author
        return self

    def user(self, user):
        if user is not None:
            self.filter['comments.user'] = user
        return self

    def after(self, after):
        if after is not None:
            if not self.sort[0] in self.filter:
                self.filter[self.sort[0]] = {}
            self.filter[self.sort[0]]['$gt'] = dateutil.parser.parse(after)
        return self

    def before(self, before):
        if before is not None:
            if not self.sort[0] in self.filter:
                self.filter[self.sort[0]] = {}
            self.filter[self.sort[0]]['$lt'] = dateutil.parser.parse(before)
        return self

    def comments(self, amount_of_comments):
        if amount_of_comments is not None:
            # A comment of the note counts as everything after the original comment
            self.filter['comments'] = {
                '$size': int(amount_of_comments) + 1
            }
        return self

    def commented(self, commented):
        if commented not in [None, 'include', 'hide', 'only']:
            raise ValueError('Commented must be one of [include, hide, only]')

        if commented is not None:
            # Filtering out commented notes means that only the original comment exists
            if commented == 'hide':
                self.filter['comments'] = {
                    '$size': 1
                }
            # Showing only commented notes requires the amount of comments to be greater than 1
            # This is not directly allowed (since $size does not accept ranges of values, e.g. via $gt),
            # so instead show only notes with an amount of comments different from 1
            # (notes with 0 comments do not exist)
            if commented == 'only':
                self.filter['comments'] = {
                    '$not': { '$size': 1 }
                }
        return self


class BoundingBox(object):
    def __init__(self, bbox):
        bbox = [float(x) for x in bbox.split(',')]
        if len(bbox) != 4:
            raise ValueError('The bounding box does not contain all required coordinates')

        self.x1 = bbox[0]
        self.y1 = bbox[1]
        self.x2 = bbox[2]
        self.y2 = bbox[3]
        self.check()

    def check(self):
        if self.x1 > self.x2:
            raise ValueError('The minimum longitude must be smaller than the maximum longitude')
        if self.y1 > self.y2:
            raise ValueError('The minimum latitude must be smaller than the maximum latitude')
        if self.x1 < -180 or self.y1 < -90 or self.x2 > +180 or self.y2 > +90:
            raise ValueError('The bounding box exceeds the size of the world, please specify a smaller bounding box')
