import dateutil

class Note(object):
    def __init__(self, feature):
        self.id = feature['properties']['id']
        self.coordinates = feature['geometry']['coordinates']
        self.status = feature['properties']['status']

        comments = self.comments(feature['properties']['comments'])
        self.comments = comments
        self.updated_at = None if len(comments) == 0 else comments[-1]['date']
        # If there are no comments, the note is basically useless, throws no error for now as it is filtered out in another function
        if len(comments) == 0: print(feature)

    # Parse the comments and extract only the useful information
    def comments(self, comments):
        for comment in comments:
            if 'date' in comment:
                comment['date'] = dateutil.parser.parse(comment['date'], ignoretz=True)
            if 'user_url' in comment:
                del comment['user_url']
            if 'html' in comment:
                del comment['html']
            if not comment['text']:
                del comment['text']
        return comments

    # Return the necessary values as a dictionary (needed by MongoDB)
    def to_dict(self):
        return {
            '_id': self.id,
            'coordinates': self.coordinates,
            'status': self.status,
            'updated_at': self.updated_at,
            'comments': self.comments
        }
