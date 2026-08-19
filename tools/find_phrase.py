#!/usr/bin/env python3
"""Locate a literal phrase across the project's text files.

Usage:
    python3 tools/find_phrase.py "量化测算" [--root DIR] [--ext md,py,json]

Prints every match as: <file>:<line>  <content>
Exit code 0 if at least one match, 1 if none.
"""
import argparse
import os
import sys

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DEFAULT_EXTS = {"md", "py", "json", "txt", "yaml", "yml", "toml"}
SKIP_DIRS = {".git", ".kilo", "venv", "__pycache__", "node_modules",
             ".codebuddy", ".vscode", "dist", "build"}


def iter_text_files(root: str, exts: set):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.rsplit(".", 1)[-1].lower() in exts:
                yield os.path.join(dirpath, fn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phrase", help="literal phrase to search for")
    ap.add_argument("--root", default=".", help="search root (default: cwd)")
    ap.add_argument("--ext", default=",".join(sorted(DEFAULT_EXTS)),
                    help="comma-separated extensions to include")
    args = ap.parse_args()

    phrase = args.phrase
    exts = {e.strip().lower() for e in args.ext.split(",") if e.strip()}
    root = os.path.abspath(args.root)

    matches = 0
    for path in iter_text_files(root, exts):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if phrase in line:
                        matches += 1
                        rel = os.path.relpath(path, root)
                        print(f"{rel}:{i}\t{line.rstrip()}")
        except (UnicodeDecodeError, OSError):
            continue

    if matches == 0:
        print(f"No matches for '{phrase}'", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
