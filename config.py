import os

from dotenv import load_dotenv

load_dotenv()

config = dict(
    DEFAULT_LIMIT=50,
    MAX_LIMIT=250,
    ROOT_PATH=os.path.dirname(os.path.realpath(__file__)),
    DB_USER=os.environ.get('DB_USER'),
    DB_PASSWORD=os.environ.get('DB_PASSWORD'),
    DB_HOST=os.environ.get('DB_HOST'),
    TOKEN_SECRET=os.environ.get('TOKEN_SECRET'),
    CORS_ORIGINS='*',
    CORS_ALWAYS_SEND=False,
)
