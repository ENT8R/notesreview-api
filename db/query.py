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
            self.filter['$text'] = {
                '$search': query
            }
        return self

    def status(self, status):
        if status not in [None, 'open', 'closed']:
            raise ValueError('Status must be one of [open, closed]')

        if status is not None:
            self.filter['status'] = status
        return self

    def anonymous(self, anonymous):
        if anonymous is not None and anonymous == 'false':
            # Filtering out anonymous notes means that there must be a user who created the note
            self.filter['comments.0.user'] = {
                '$exists': True
            }
        return self

    def author(self, author):
        if author is not None:
            self.filter['comments.0.user'] = author
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
