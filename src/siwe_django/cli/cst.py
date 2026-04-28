"""libcst-based mutators for ``settings.py`` / root ``urls.py``.

Each mutator is idempotent: running it twice leaves the file in the same
state as running it once. This keeps the wizard safe to re-run when adopters
change their minds.
"""

from __future__ import annotations

from collections.abc import Iterable

import libcst as cst
from libcst import matchers as m


def _string_node(value: str) -> cst.SimpleString:
    return cst.SimpleString(value=f'"{value}"')


def _is_target_assign(stmt: cst.SimpleStatementLine, name: str) -> bool:
    if not stmt.body or not isinstance(stmt.body[0], cst.Assign):
        return False
    targets = stmt.body[0].targets
    return any(
        isinstance(t.target, cst.Name) and t.target.value == name for t in targets
    )


def _list_already_contains(node: cst.BaseExpression, needle: str) -> bool:
    return m.matches(
        node,
        m.List(
            elements=[
                m.ZeroOrMore(),
                m.Element(value=m.SimpleString(value=f'"{needle}"')),
                m.ZeroOrMore(),
            ]
        ),
    ) or m.matches(
        node,
        m.List(
            elements=[
                m.ZeroOrMore(),
                m.Element(value=m.SimpleString(value=f"'{needle}'")),
                m.ZeroOrMore(),
            ]
        ),
    )


def _append_to_list(
    list_node: cst.List, value: str, *, prepend: bool = False
) -> cst.List:
    if _list_already_contains(list_node, value):
        return list_node
    new_element = cst.Element(value=_string_node(value))
    elements = list(list_node.elements)
    if prepend:
        elements.insert(0, new_element)
    else:
        elements.append(new_element)
    return list_node.with_changes(elements=elements)


class _ListAppendTransformer(cst.CSTTransformer):
    def __init__(self, name: str, values: Iterable[str], *, prepend: bool):
        self.name = name
        self.values = list(values)
        self.prepend = prepend
        self.modified = False
        self.created = False

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        new_body: list[cst.BaseStatement] = []
        seen = False
        for stmt in updated_node.body:
            if isinstance(stmt, cst.SimpleStatementLine) and _is_target_assign(
                stmt, self.name
            ):
                seen = True
                new_body.append(self._mutate_assign(stmt))
            else:
                new_body.append(stmt)
        if not seen:
            new_body.append(self._build_assign())
            self.created = True
        return updated_node.with_changes(body=new_body)

    def _mutate_assign(
        self, stmt: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine:
        assign = stmt.body[0]
        assert isinstance(assign, cst.Assign)
        if not isinstance(assign.value, cst.List):
            return stmt
        list_node = assign.value
        for value in self.values:
            new_list = _append_to_list(list_node, value, prepend=self.prepend)
            if new_list is not list_node:
                self.modified = True
            list_node = new_list
        new_assign = assign.with_changes(value=list_node)
        return stmt.with_changes(body=[new_assign])

    def _build_assign(self) -> cst.SimpleStatementLine:
        elements = [cst.Element(value=_string_node(v)) for v in self.values]
        list_node = cst.List(elements=elements)
        target = cst.AssignTarget(target=cst.Name(self.name))
        return cst.SimpleStatementLine(
            body=[cst.Assign(targets=[target], value=list_node)]
        )


def add_to_list_setting(
    source: str, name: str, values: Iterable[str], *, prepend: bool = False
) -> str:
    """Add ``values`` to the list assigned to ``name`` (creating the list if
    absent). When ``prepend`` is True new entries are inserted at the start —
    use this for ``AUTHENTICATION_BACKENDS`` so SiweBackend wins over the
    default ``ModelBackend``.
    """
    module = cst.parse_module(source)
    transformer = _ListAppendTransformer(name, values, prepend=prepend)
    new_module = module.visit(transformer)
    return new_module.code


def _has_top_level_assign(module: cst.Module, name: str) -> bool:
    return any(
        isinstance(stmt, cst.SimpleStatementLine)
        and _is_target_assign(stmt, name)
        for stmt in module.body
    )


def add_settings_block(source: str, block_code: str, *, name: str) -> str:
    """Append ``block_code`` to ``source`` if a top-level ``name = ...``
    assignment is not already present. ``block_code`` is appended verbatim and
    must contain its own assignment (e.g. ``\"SIWE_DJANGO = {...}\"``).
    """
    module = cst.parse_module(source)
    if _has_top_level_assign(module, name):
        return module.code
    addition = cst.parse_module(block_code).body
    new_body = list(module.body) + list(addition)
    return module.with_changes(body=new_body).code


def ensure_url_include(source: str, route: str, dotted_path: str) -> str:
    """Ensure root ``urls.py`` mounts ``include("siwe_django.urls")`` (or
    similar) at ``route``. Idempotent.
    """
    if dotted_path in source and route in source:
        return source
    module = cst.parse_module(source)
    has_include = any(
        m.matches(
            stmt,
            m.SimpleStatementLine(
                body=[
                    m.ImportFrom(
                        module=m.Attribute() | m.Name(),
                        names=m.OneOf(
                            m.ImportStar(),
                            [
                                m.ZeroOrMore(),
                                m.ImportAlias(name=m.Name("include")),
                                m.ZeroOrMore(),
                            ],
                        ),
                    )
                ]
            ),
        )
        for stmt in module.body
        if isinstance(stmt, cst.SimpleStatementLine)
    )
    new_body = list(module.body)
    if not has_include:
        new_body.insert(
            0,
            cst.parse_statement("from django.urls import include, path"),
        )

    inserted = False
    for index, stmt in enumerate(new_body):
        if isinstance(stmt, cst.SimpleStatementLine) and _is_target_assign(
            stmt, "urlpatterns"
        ):
            assign = stmt.body[0]
            assert isinstance(assign, cst.Assign)
            if isinstance(assign.value, cst.List):
                new_element = cst.Element(
                    value=cst.Call(
                        func=cst.Name("path"),
                        args=[
                            cst.Arg(value=_string_node(route)),
                            cst.Arg(
                                value=cst.Call(
                                    func=cst.Name("include"),
                                    args=[cst.Arg(value=_string_node(dotted_path))],
                                )
                            ),
                        ],
                    )
                )
                elements = [*assign.value.elements, new_element]
                new_value = assign.value.with_changes(elements=elements)
                new_assign = assign.with_changes(value=new_value)
                new_body[index] = stmt.with_changes(body=[new_assign])
                inserted = True
                break

    if not inserted:
        new_body.append(
            cst.parse_statement(
                f'urlpatterns = [path("{route}", include("{dotted_path}"))]'
            )
        )

    return cst.Module(body=new_body).code
