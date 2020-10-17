import dateutil.parser
from flask import Flask, Response, request

from bson import json_util
from pymongo import MongoClient

client = MongoClient('mongodb://127.0.0.1:27017/')
collection = client.notesreview.notes

app = Flask(__name__)

@app.route('/')
def search():
    # Figure out how to sort the results
    sort_by = request.args.get('sort_by', 'updated_at')
    if sort_by not in ['updated_at', 'created_at']:
        return {'error': 'sort must be one of [updated_at, created_at]'}, 400
    sort_by = 'comments.0.date' if sort_by == 'created_at' else 'updated_at'

    order = request.args.get('order', 'descending')
    if order not in ['desc', 'descending', 'asc', 'ascending']:
        return {'error': 'order must be one of [desc, descending, asc, ascending]'}, 400
    order = 1 if order in ['asc', 'ascending'] else -1
    sort = [(sort_by, order)]

    #----------------------------------------#

    # Build the actual filter and query
    query = request.args.get('query') # A word or sentence which can be found in the comments
    status = request.args.get('status') # Whether the note is already closed or still open
    if status not in [None, 'open', 'closed']:
        return {'error': 'status must be one of [open, closed]'}, 400

    anonymous = request.args.get('anonymous', 'true') # Whether anonymous notes should be included in the results
    author = request.args.get('author') # Filter only notes created by this user

    after = request.args.get('after', type=dateutil.parser.parse) # Filter only notes updated/created after this date
    before = request.args.get('before', type=dateutil.parser.parse) # Filter only notes updated/created before this date

    amount_of_comments = request.args.get('comments', type=int) # Filters the amount of comments on a note
    filter = build_filter(query, status, anonymous, author, sort_by, after, before, amount_of_comments)

    #----------------------------------------#

    # Set the fitting limit
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000
    limit = request.args.get('limit', DEFAULT_LIMIT, type=int)
    if limit > MAX_LIMIT:
        return {'error': 'Limit must not be higher than %d' % MAX_LIMIT}, 400
    if limit == 0: limit = DEFAULT_LIMIT # Prevent that a limit of 0 is treated as no limit at all

    print('FILTER:', filter)
    print('LIMIT:', limit)
    print('SORT:', sort)
    result = collection.find(filter=filter, limit=limit, sort=sort)
    return Response(
        json_util.dumps(result, json_options=json_util.STRICT_JSON_OPTIONS),
        mimetype='application/json'
    )

def build_filter(query, status, anonymous, author, sort_by, after, before, amount_of_comments):
    filter = {}
    if query is not None:
        filter['$text'] = {
            '$search': query
        }
    if status is not None:
        filter['status'] = status
    if anonymous is not None and anonymous == 'false':
        # Filtering out anonymous notes means that there must be a user who created the note
        filter['comments.0.user'] = {
            '$exists': True
        }
    if author is not None:
        filter['comments.0.user'] = author
    if after is not None or before is not None:
        filter[sort_by] = {}
    if after is not None:
        filter[sort_by]['$gt'] = after
    if before is not None:
        filter[sort_by]['$lt'] = before
    if amount_of_comments is not None:
        # A comment of the note counts as everything after the original comment
        filter['comments'] = {
            '$size': amount_of_comments + 1
        }
    return filter

if __name__ == '__main__':
    app.run(debug=True, port=5000)
