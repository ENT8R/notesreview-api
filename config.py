import dataclasses
import os
from collections.abc import Iterator
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f'Missing environment variable: {name}')
    return value


@dataclass(frozen=True)
class Config:
    # fmt: off
    DEFAULT_LIMIT: int = 50
    MAX_LIMIT: int = 500
    BLOCKLIST_LIMIT: int = 500
    WATCHLIST_LIMIT: int = 500

    ROOT_PATH: str = os.path.dirname(os.path.realpath(__file__))

    DB_USER: str = env('DB_USER')
    DB_PASSWORD: str = env('DB_PASSWORD')
    DB_HOST: str = env('DB_HOST')

    OPENSTREETMAP_OAUTH_JWKS_URI: str = env('OPENSTREETMAP_OAUTH_JWKS_URI')
    OPENSTREETMAP_OAUTH_CLIENT_ID: str = env('OPENSTREETMAP_OAUTH_CLIENT_ID')

    CORS_ORIGINS: str = '*'
    CORS_ALLOW_HEADERS: list[str] = field(default_factory=lambda: ['Authorization', 'Content-Type'])
    CORS_ALWAYS_SEND: bool = False
    # fmt: on

    def __iter__(self) -> Iterator:
        return iter(dataclasses.asdict(self).items())
