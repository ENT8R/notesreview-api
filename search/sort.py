from typing import Self


class Sort(object):
    def build(self) -> tuple[str | None, int]:
        return self._by, self._order

    def by(self, by: str | None, default: str) -> Self:
        if by is None:
            by = default

        allowed = ['none', 'updated_at', 'created_at']
        if by not in allowed:
            raise ValueError(f'Sort must be one of {allowed}')

        if by == 'none':
            self._by = None
        elif by == 'updated_at':
            self._by = 'updated_at'
        elif by == 'created_at':
            self._by = 'comments.0.date'
        return self

    def order(self, order: str | None, default: str) -> Self:
        if order is None:
            order = default

        allowed = ['desc', 'descending', 'asc', 'ascending']
        if order not in allowed:
            raise ValueError(f'Order must be one of {allowed}')

        if order in ['asc', 'ascending']:
            self._order = 1
        elif order in ['desc', 'descending']:
            self._order = -1
        return self
