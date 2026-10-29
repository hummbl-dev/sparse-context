# sparse-context

[![CI](https://github.com/hummbl-dev/sparse-context/actions/workflows/ci.yml/badge.svg)](https://github.com/hummbl-dev/sparse-context/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> AST-level semantic context compressor for LLMs: extracts function signatures, docstrings, and contracts while pruning execution bodies, saving 70-85% token budget.

## Overview

Feeding whole codebases into LLM context windows is expensive and fills context with implementation details (loops, intermediate math, internal local variables) that agents rarely need when reasoning about architecture or calling interfaces.

`sparse-context` compresses code using Python's native AST parser:
- **Skeletonizes**: Collapses function and method bodies into `...` while preserving type annotations, default parameters, decorators, and docstrings.
- **Extracts Contracts**: Retains class definitions, dataclass fields, type aliases, and module docstrings.
- **Budget-Aware Packing**: Assembles whole repository contexts into strict token limits (e.g. 4k, 8k, 32k tokens) with configurable focus files kept in full.
- **Zero Dependencies**: Pure Python 3.11+ standard library.

## Installation

```bash
pip install sparse-context
```

Or install from source:

```bash
git clone https://github.com/hummbl-dev/sparse-context.git
cd sparse-context
pip install .
```

## Quick Start

### 1. Skeletonize a Python File
```bash
sparse-context skeletonize path/to/large_module.py
```

### 2. Inspect Compression Stats
```bash
sparse-context stats path/to/large_module.py
```
Output:
```text
File: path/to/large_module.py
  * Classes/Functions: 14
  * Original Tokens:   ~4200
  * Skeleton Tokens:   ~650
  * Token Reduction:   84.5%
```

### 3. Pack Repository into Token Budget
Compress an entire codebase into an 8,000-token prompt context, keeping `api.py` in full:
```bash
sparse-context pack ./src --budget 8000 --focus src/api.py -o prompt_context.md
```

## License

Apache-2.0
