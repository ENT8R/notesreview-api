import os
from typing import Any

import lark


class Users(object):
    def __init__(self) -> None:
        with open(
            os.path.join(os.path.dirname(__file__), 'grammars', 'users.lark')
        ) as file:
            self.grammar = lark.Lark(file.read())

    def parse(self, input: str) -> tuple[list[Any], list[Any]]:
        tree = self.grammar.parse(input)
        include = []
        exclude = []

        for node in tree.children:
            if not isinstance(node, lark.Tree):
                continue
            expression = node.children[0]
            if isinstance(expression, lark.Token):
                include.append(expression.value)
            elif (
                isinstance(expression, lark.Tree) and expression.data == 'not'
            ):
                exclude.append(expression.children[0])

        if len(include) + len(exclude) > 10:
            raise ValueError(
                'The amount of users to search for exceeds the limit'
            )

        return include, exclude
