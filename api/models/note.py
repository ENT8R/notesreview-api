import datetime
from dataclasses import dataclass

from .comment import Comment


@dataclass
class Note:
    _id: int
    coordinates: tuple[float, float]
    status: str
    updated_at: datetime.datetime
    comments: list[Comment]
