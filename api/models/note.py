import datetime
from dataclasses import dataclass
from typing import List, Tuple

from .comment import Comment


@dataclass
class Note:
    _id: int
    coordinates: Tuple[float, float]
    status: str
    updated_at: datetime.datetime
    comments: List[Comment]
