import datetime
from dataclasses import dataclass


@dataclass
class Comment:
    date: datetime.datetime
    action: str
    uid: int
    user: str
    text: str
