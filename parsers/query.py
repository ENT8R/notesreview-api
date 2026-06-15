import os
import re
from typing import Any

import lark


class Query(object):
    def __init__(self) -> None:
        self.allowed_keywords = ('$and', '$or', '$nor')
        with open(
            os.path.join(os.path.dirname(__file__), 'grammars', 'query.lark')
        ) as file:
            self.grammar = lark.Lark(file.read())

    def parse(self, input: str | None, scope: str) -> dict[str, Any]:
        if input is not None:
            try:
                tree = self.grammar.parse(input)
                return QueryInterpreter(scope).visit(tree)
            except lark.exceptions.UnexpectedInput as error:
                raise ValueError(str(error) + error.get_context(input))
        return {}


class QueryInterpreter(lark.visitors.Interpreter):
    def __init__(self, scope: str) -> None:
        self.scope = scope

    # Build an $or combination of all children by visiting them
    def or_exp(self, tree: lark.Tree) -> dict[str, Any]:
        return {
            '$or': self.visit_children(tree),
        }

    # Build an $and combination of all children by visiting them
    def and_exp(self, tree: lark.Tree) -> dict[str, Any]:
        return {
            '$and': self.visit_children(tree),
        }

    # The child of a literal is an atomic expression or its negated form.
    # If nested expressions are allowed by the grammar, a literal can also have AND/OR
    # expressions as its child, otherwise only tokens or NOT expressions are possible
    def literal(self, tree: lark.Tree) -> dict[str, Any]:
        # Expect only a single child and raise an error if this is not the case
        if len(tree.children) != 1:
            raise ValueError('A literal can only have a single child')

        # If the child of this literal is a token, construct the expression of the term directly,
        # otherwise visit the child (i.e. in case of negations or nested expressions)
        if type(tree.children[0]) is lark.lexer.Token:
            return {
                self.scope: self._term(tree.children[0]),
            }
        else:
            return self.visit(tree.children[0])

    # Build a negated expression of the child by constructing the expression directly.
    # This works only if the child is a token or a token embedded in a literal.
    # If nested expressions are allowed by the grammar, a negated expression can also have
    # AND/OR expressions as its child, which will need to be visited as well
    def not_exp(self, tree: lark.Tree) -> dict[str, Any]:
        # Expect only a single child and raise an error if this is not the case
        if len(tree.children) != 1:
            raise ValueError(
                'A negated expression can only have a single child'
            )

        if type(tree.children[0]) is lark.lexer.Token:
            # NOT TERM
            return {
                self.scope: {
                    '$not': self._term(tree.children[0]),
                }
            }
        elif (
            tree.children[0].data == 'literal'
            and type(tree.children[0].children[0]) is lark.lexer.Token
        ):
            # NOT (TERM)
            return {
                self.scope: {
                    '$not': self._term(tree.children[0].children[0]),
                }
            }
        elif tree.children[0].data == 'or_exp':
            # NOT (and_exp OR and_exp)
            return {
                '$nor': self.visit_children(tree),
            }
        else:
            # NOT (literal AND literal)
            return {
                '$nor': [self.visit(tree.children[0])],
            }

    def _term(self, token: lark.lexer.Token) -> dict[str, str]:
        # Remove leading and trailing quotation marks from the string
        value = token.value
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Use a regex search in order to find the correct documents
        return {
            '$regex': (
                value.removeprefix('regex:')
                if value.startswith('regex:')
                else re.escape(value)
            ),
            '$options': 'i',
        }
