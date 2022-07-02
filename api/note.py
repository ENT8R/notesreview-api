import datetime
from dataclasses import dataclass
from typing import List

from .comment import Comment


@dataclass
class Note:
    _id: int
    coordinates: List[float]
    status: str
    updated_at: datetime.datetime
    comments: List[Comment]
