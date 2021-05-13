import dateutil.parser

class Filter(object):
    def __init__(self, sort_by):
        self.filter = {}
        self.sort_by = sort_by

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
            if not self.sort_by in self.filter:
                self.filter[self.sort_by] = {}
            self.filter[self.sort_by]['$gt'] = dateutil.parser.parse(after)
        return self

    def before(self, before):
        if before is not None:
            if not self.sort_by in self.filter:
                self.filter[self.sort_by] = {}
            self.filter[self.sort_by]['$lt'] = dateutil.parser.parse(before)
        return self

    def comments(self, amount_of_comments):
        if amount_of_comments is not None:
            # A comment of the note counts as everything after the original comment
            self.filter['comments'] = {
                '$size': int(amount_of_comments) + 1
            }
        return self

    def build(self):
        return self.filter
