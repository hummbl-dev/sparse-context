"""AST skeletonizer that prunes execution bodies while preserving contracts."""

from __future__ import annotations

import ast
from pathlib import Path


class SkeletonTransformer(ast.NodeTransformer):
    """Replaces function and method bodies with an Ellipsis while keeping docstrings."""

    def __init__(self, keep_docstrings: bool = True) -> None:
        self.keep_docstrings = keep_docstrings

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._prune_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._prune_body(node)

    def _prune_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        # Check if the first statement is a docstring
        new_body: list[ast.stmt] = []
        doc = ast.get_docstring(node) if self.keep_docstrings else None

        if doc is not None and node.body:
            # Preserve the docstring node
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
                new_body.append(first_stmt)

        # Append Ellipsis constant: `...`
        ellipsis_expr = ast.Expr(value=ast.Constant(value=...))
        new_body.append(ellipsis_expr)

        node.body = new_body
        return node


def skeletonize_source(source_code: str, keep_docstrings: bool = True) -> str:
    """Transform python source code into a pruned contract skeleton."""
    tree = ast.parse(source_code)
    transformer = SkeletonTransformer(keep_docstrings=keep_docstrings)
    transformed = transformer.visit(tree)
    ast.fix_missing_locations(transformed)
    return ast.unparse(transformed)


def skeletonize_file(path: Path | str, keep_docstrings: bool = True) -> str:
    """Skeletonize a python source file from disk."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return skeletonize_source(content, keep_docstrings=keep_docstrings)
