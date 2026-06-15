from typing import Self


class Limit(object):
    def __init__(self, input: str | None) -> None:
        self.input = input

    def default(self, default: int) -> Self:
        self._default = default
        return self

    def max(self, max: int) -> Self:
        self._max = max
        return self

    def build(self) -> int:
        if self._default is None:
            raise ValueError(
                'Set a default limit by calling default() before calling build()'
            )

        if self._max is None:
            raise ValueError(
                'Set a maximum limit by calling max() before calling build()'
            )

        if self.input is None:
            return self._default

        # Apply the default limit in case the argument could not be parsed (e.g. for limit=NaN)
        try:
            limit = int(self.input) if self.input else self._default
        except ValueError:
            limit = self._default

        if limit > self._max:
            raise ValueError(f'Limit must not be higher than {self._max}.')

        # Prevent that a limit of 0 is treated as no limit at all
        if limit == 0:
            limit = self._default

        return limit
