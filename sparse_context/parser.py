"""AST symbol extractor and dependency inspector."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class SymbolInfo:
    name: str
    kind: str  # "class", "function", "async_function", "variable", "import"
    lineno: int
    docstring: Optional[str] = None
    args: List[str] = field(default_factory=list)
    returns: Optional[str] = field(default=None)
    decorators: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class ModuleProfile:
    path: str
    docstring: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    raw_char_count: int = 0
    estimated_tokens: int = 0


class ASTSymbolExtractor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: List[SymbolInfo] = []
        self.imports: List[str] = []
        self.docstring: Optional[str] = None
        self._current_class: Optional[str] = None

    def visit_Module(self, node: ast.Module) -> None:
        self.docstring = ast.get_docstring(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name + (f" as {alias.asname}" if alias.asname else "")
            self.imports.append(f"import {name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        aliases = [a.name + (f" as {a.asname}" if a.asname else "") for a in node.names]
        self.imports.append(f"from {mod} import {', '.join(aliases)}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        decorators = [ast.unparse(d) for d in node.decorator_list]
        prev = self._current_class
        self._current_class = node.name
        self.symbols.append(
            SymbolInfo(
                name=node.name,
                kind="class",
                lineno=node.lineno,
                docstring=ast.get_docstring(node),
                decorators=decorators,
            )
        )
        self.generic_visit(node)
        self._current_class = prev

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_func(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_func(node, "async_function")
        self.generic_visit(node)

    def _process_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        name = f"{self._current_class}.{node.name}" if self._current_class else node.name
        decorators = [ast.unparse(d) for d in node.decorator_list]
        args_repr = [a.arg for a in node.args.args]
        returns_repr = ast.unparse(node.returns) if node.returns else None

        self.symbols.append(
            SymbolInfo(
                name=name,
                kind=kind,
                lineno=node.lineno,
                docstring=ast.get_docstring(node),
                args=args_repr,
                returns=returns_repr,
                decorators=decorators,
            )
        )


def analyze_source(source_code: str, file_path: str = "<source>") -> ModuleProfile:
    """Analyze python source code into a ModuleProfile."""
    tree = ast.parse(source_code, filename=file_path)
    extractor = ASTSymbolExtractor()
    extractor.visit(tree)

    char_count = len(source_code)
    estimated_tokens = max(1, char_count // 4)

    return ModuleProfile(
        path=file_path,
        docstring=extractor.docstring,
        imports=extractor.imports,
        symbols=extractor.symbols,
        raw_char_count=char_count,
        estimated_tokens=estimated_tokens,
    )


def analyze_file(path: Path | str) -> ModuleProfile:
    """Analyze a python file on disk."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return analyze_source(content, str(p))
