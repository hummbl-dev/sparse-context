"""Unit tests for sparse-context."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparse_context.cli import main
from sparse_context.packer import ContextPacker, estimate_tokens
from sparse_context.parser import analyze_source
from sparse_context.skeletonizer import skeletonize_source


SAMPLE_CODE = """\"\"\"Module docstring.\"\"\"

import os
from typing import Optional

GLOBAL_CONST: int = 42

class DataProcessor:
    \"\"\"Processes complex enterprise data.\"\"\"
    multiplier: int = 2

    def __init__(self, name: str) -> None:
        \"\"\"Initialize processor.\"\"\"
        self.name = name
        self.count = 0
        for i in range(100):
            self.count += i * self.multiplier

    @property
    def ready(self) -> bool:
        \"\"\"Check if ready.\"\"\"
        return self.count > 0

    async def compute(self, factor: float = 1.0) -> float:
        \"\"\"Async compute operation.\"\"\"
        total = 0.0
        for j in range(500):
            total += j * factor
        return total


def standalone_worker(x: int, y: int) -> int:
    \"\"\"Adds two numbers after heavy processing.\"\"\"
    result = 0
    for _ in range(1000):
        result += x + y
    return result
"""


class TestASTParser(unittest.TestCase):
    def test_analyze_source(self):
        profile = analyze_source(SAMPLE_CODE, "sample.py")
        self.assertEqual(profile.docstring, "Module docstring.")
        self.assertEqual(len(profile.imports), 2)
        symbols = {s.name: s for s in profile.symbols}

        self.assertIn("DataProcessor", symbols)
        self.assertEqual(symbols["DataProcessor"].kind, "class")
        self.assertEqual(symbols["DataProcessor"].docstring, "Processes complex enterprise data.")

        self.assertIn("DataProcessor.__init__", symbols)
        self.assertIn("DataProcessor.compute", symbols)
        self.assertEqual(symbols["DataProcessor.compute"].kind, "async_function")

        self.assertIn("standalone_worker", symbols)
        self.assertEqual(symbols["standalone_worker"].kind, "function")
        self.assertEqual(symbols["standalone_worker"].args, ["x", "y"])


class TestSkeletonizer(unittest.TestCase):
    def test_skeletonize_with_docstrings(self):
        skel = skeletonize_source(SAMPLE_CODE, keep_docstrings=True)
        self.assertIn("class DataProcessor:", skel)
        self.assertIn("Processes complex enterprise data.", skel)
        self.assertIn("...", skel)
        self.assertNotIn("for _ in range(1000):", skel)
        self.assertNotIn("self.count += i * self.multiplier", skel)
        self.assertIn("def standalone_worker(x: int, y: int) -> int:", skel)
        self.assertIn("Adds two numbers after heavy processing.", skel)

    def test_skeletonize_without_docstrings(self):
        skel = skeletonize_source(SAMPLE_CODE, keep_docstrings=False)
        self.assertNotIn("Adds two numbers after heavy processing.", skel)
        self.assertIn("...", skel)


class TestContextPacker(unittest.TestCase):
    def test_packer_in_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_dir = Path(tmpdir)
            f1 = p_dir / "mod1.py"
            f2 = p_dir / "mod2.py"
            f1.write_text(SAMPLE_CODE, encoding="utf-8")
            f2.write_text("def simple():\n    return 123\n", encoding="utf-8")

            packer = ContextPacker(token_budget=500)
            packed = packer.pack_directory(p_dir)
            self.assertGreater(packed.total_tokens, 0)
            self.assertLessEqual(packed.total_tokens, 500)
            self.assertEqual(len(packed.files), 2)
            self.assertGreater(packed.compression_ratio, 0.0)

            md = packed.render_markdown()
            self.assertIn("Compressed Repository Context", md)
            self.assertIn("mod1.py", md)

    def test_packer_focus_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_dir = Path(tmpdir)
            f1 = p_dir / "core.py"
            f1.write_text(SAMPLE_CODE, encoding="utf-8")

            packer = ContextPacker(token_budget=10000)
            packed = packer.pack_directory(p_dir, focus_files=["core.py"])
            self.assertEqual(len(packed.files), 1)
            self.assertEqual(packed.files[0].mode, "full")


class TestCLI(unittest.TestCase):
    def test_cli_skeletonize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text(SAMPLE_CODE, encoding="utf-8")
            code = main(["skeletonize", str(f)])
            self.assertEqual(code, 0)

    def test_cli_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text(SAMPLE_CODE, encoding="utf-8")
            code = main(["stats", str(f)])
            self.assertEqual(code, 0)

    def test_cli_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_dir = Path(tmpdir)
            (p_dir / "a.py").write_text(SAMPLE_CODE, encoding="utf-8")
            out_file = p_dir / "context.md"
            code = main(["pack", str(p_dir), "-b", "2000", "-o", str(out_file)])
            self.assertEqual(code, 0)
            self.assertTrue(out_file.exists())
            self.assertIn("Compressed Repository Context", out_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
