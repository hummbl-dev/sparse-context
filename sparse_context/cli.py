"""CLI interface for sparse-context."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sparse_context import __version__
from sparse_context.packer import ContextPacker, estimate_tokens
from sparse_context.parser import analyze_file
from sparse_context.skeletonizer import skeletonize_file, skeletonize_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sparse-context",
        description="AST-level semantic context compressor for LLMs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: skeletonize
    skel_p = subparsers.add_parser("skeletonize", help="Generate AST contract skeleton for a file")
    skel_p.add_argument("file", help="Python source file to skeletonize")
    skel_p.add_argument("--no-docstrings", action="store_true", help="Strip docstrings as well")

    # Subcommand: pack
    pack_p = subparsers.add_parser("pack", help="Pack directory into token-budgeted prompt context")
    pack_p.add_argument("directory", help="Target codebase directory")
    pack_p.add_argument("-b", "--budget", type=int, default=8000, help="Max token budget (default: 8000)")
    pack_p.add_argument("-f", "--focus", help="Comma-separated relative paths of files to keep in full")
    pack_p.add_argument("-o", "--output", help="Output file path (default: stdout)")

    # Subcommand: stats
    stats_p = subparsers.add_parser("stats", help="Compute compression stats for a file")
    stats_p.add_argument("file", help="Python source file to inspect")

    args = parser.parse_args(argv)

    if args.command == "skeletonize":
        p = Path(args.file)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 1
        output = skeletonize_file(p, keep_docstrings=not args.no_docstrings)
        print(output)
        return 0

    elif args.command == "pack":
        p = Path(args.directory)
        if not p.exists() or not p.is_dir():
            print(f"Error: Directory not found: {p}", file=sys.stderr)
            return 1

        focus_list = [f.strip() for f in args.focus.split(",")] if args.focus else []
        packer = ContextPacker(token_budget=args.budget)
        packed = packer.pack_directory(p, focus_files=focus_list)
        rendered = packed.render_markdown()

        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
            print(f"[+] Context packed: {packed.total_tokens}/{packed.budget} tokens ({packed.compression_ratio:.1%} reduction) written to {args.output}")
        else:
            print(rendered)
        return 0

    elif args.command == "stats":
        p = Path(args.file)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 1

        profile = analyze_file(p)
        raw_code = p.read_text(encoding="utf-8")
        skel = skeletonize_source(raw_code)

        orig_tok = estimate_tokens(raw_code)
        skel_tok = estimate_tokens(skel)
        reduction = max(0.0, (orig_tok - skel_tok) / orig_tok) if orig_tok > 0 else 0.0

        print(f"File: {p}")
        print(f"  * Classes/Functions: {len(profile.symbols)}")
        print(f"  * Original Tokens:   ~{orig_tok}")
        print(f"  * Skeleton Tokens:   ~{skel_tok}")
        print(f"  * Token Reduction:   {reduction:.1%}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
