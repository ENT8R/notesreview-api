from sanic import Blueprint

from .blocklist import blueprint as blocklist
from .watchlist import blueprint as watchlist

blueprint = Blueprint.group(blocklist, watchlist, url_prefix='/notes')
