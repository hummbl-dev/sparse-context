"""Context window packer that fits codebases into strict token budgets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sparse_context.skeletonizer import skeletonize_source


@dataclass
class PackedFile:
    path: str
    mode: str  # "full" or "skeleton"
    char_count: int
    estimated_tokens: int
    content: str


@dataclass
class PackedContext:
    total_tokens: int
    budget: int
    files: List[PackedFile]
    compression_ratio: float  # (original - packed) / original

    def render_markdown(self) -> str:
        """Render packed files into clean markdown blocks for LLM context."""
        parts = [
            f"# Compressed Repository Context (Estimated Tokens: ~{self.total_tokens}/{self.budget})",
            f"Compression ratio: {self.compression_ratio:.1%}\n",
        ]
        for f in self.files:
            parts.append(f"## File: `{f.path}` ({f.mode.upper()})")
            parts.append(f"```python\n{f.content}\n```\n")
        return "\n".join(parts)


def estimate_tokens(text: str) -> int:
    """Standard robust heuristic: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


class ContextPacker:
    """Assembles sparse and full code representations into a budget."""

    def __init__(self, token_budget: int = 8000) -> None:
        self.token_budget = token_budget

    def pack_directory(
        self,
        root_dir: Path | str,
        focus_files: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None,
    ) -> PackedContext:
        root = Path(root_dir).resolve()
        exclude = set(exclude_dirs or [".git", "__pycache__", ".venv", "venv", "build", "dist", ".pytest_cache", ".eggs"])
        focus = set(focus_files or [])

        py_files: List[Path] = []
        for path in sorted(root.rglob("*.py")):
            if any(part in exclude for part in path.parts):
                continue
            py_files.append(path)

        packed_files: List[PackedFile] = []
        accumulated_tokens = 0
        total_original_chars = 0

        # Sort priority: focus files first, then __init__.py, then shorter files
        def priority_key(p: Path) -> tuple[int, int]:
            rel = str(p.relative_to(root)).replace("\\", "/")
            is_focus = 0 if rel in focus else 1
            is_init = 0 if p.name == "__init__.py" else 1
            return (is_focus, is_init)

        sorted_files = sorted(py_files, key=priority_key)

        for p in sorted_files:
            rel_path = str(p.relative_to(root)).replace("\\", "/")
            try:
                raw_code = p.read_text(encoding="utf-8")
            except Exception:
                continue

            total_original_chars += len(raw_code)
            raw_tokens = estimate_tokens(raw_code)

            # If it's a focus file and fits, keep full
            if rel_path in focus and (accumulated_tokens + raw_tokens <= self.token_budget):
                packed_files.append(
                    PackedFile(
                        path=rel_path,
                        mode="full",
                        char_count=len(raw_code),
                        estimated_tokens=raw_tokens,
                        content=raw_code,
                    )
                )
                accumulated_tokens += raw_tokens
            else:
                # Skeletonize
                try:
                    skel = skeletonize_source(raw_code)
                except Exception:
                    skel = raw_code

                skel_tokens = estimate_tokens(skel)
                if accumulated_tokens + skel_tokens <= self.token_budget:
                    packed_files.append(
                        PackedFile(
                            path=rel_path,
                            mode="skeleton",
                            char_count=len(skel),
                            estimated_tokens=skel_tokens,
                            content=skel,
                        )
                    )
                    accumulated_tokens += skel_tokens

        original_tokens = max(1, total_original_chars // 4)
        ratio = max(0.0, (original_tokens - accumulated_tokens) / original_tokens)

        return PackedContext(
            total_tokens=accumulated_tokens,
            budget=self.token_budget,
            files=packed_files,
            compression_ratio=ratio,
        )
