import os

from dotenv import load_dotenv

load_dotenv()

# fmt: off
config = dict(
    DEFAULT_LIMIT=50,
    MAX_LIMIT=250,
    ROOT_PATH=os.path.dirname(os.path.realpath(__file__)),
    DB_USER=os.environ.get('DB_USER'),
    DB_PASSWORD=os.environ.get('DB_PASSWORD'),
    DB_HOST=os.environ.get('DB_HOST'),
    OPENSTREETMAP_OAUTH_JWKS_URI=os.environ.get('OPENSTREETMAP_OAUTH_JWKS_URI'),
    OPENSTREETMAP_OAUTH_CLIENT_ID=os.environ.get('OPENSTREETMAP_OAUTH_CLIENT_ID'),
    CORS_ORIGINS='*',
    CORS_ALWAYS_SEND=False,
)
# fmt: on
