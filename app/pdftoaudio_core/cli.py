from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extract import extract_pdf
from .jobs import init_job, inspect_status, resolve_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdftoaudio",
        description="Turn PDFs into audiobooks through inspectable local job files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a job from a source PDF")
    init_parser.add_argument("book")
    init_parser.add_argument("pdf")
    init_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show job files and next step")
    status_parser.add_argument("book")

    extract_parser = subparsers.add_parser("extract", help="Extract PDF text")
    extract_parser.add_argument("book")
    extract_parser.add_argument("--force", action="store_true")

    sanitize_parser = subparsers.add_parser(
        "sanitize",
        help="Normalize safe text characters and write sanitize reports",
    )
    sanitize_parser.add_argument("book")
    sanitize_parser.add_argument("--force", action="store_true")
    sanitize_parser.add_argument("--report-only", action="store_true")

    review_parser = subparsers.add_parser(
        "review",
        help="Flag suspicious text spans without changing text",
    )
    review_parser.add_argument("book")
    review_parser.add_argument("--force", action="store_true")

    return parser


def print_status(project_root: Path, book: str) -> int:
    paths = resolve_job(project_root, book)
    if not paths.manifest_path.exists():
        print(f"Missing job manifest: {paths.manifest_path}", file=sys.stderr)
        return 1

    status = inspect_status(paths)
    print(book)
    for display_path, state in status["files"].items():
        print(f"  {display_path:<24} {state}")

    if status["next_command"]:
        print()
        print(f"next: {status['next_command']}")
    else:
        print()
        print("next: job foundation steps complete")
    return 0


def main(argv: list[str] | None = None, project_root: Path | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    root = project_root or Path.cwd()

    try:
        if args.command == "init":
            init_job(root, args.book, Path(args.pdf), force=args.force)
            print(f"Initialized job: {args.book}")
            print(f"next: pdftoaudio extract {args.book}")
            return 0

        if args.command == "status":
            return print_status(root, args.book)

        if args.command == "extract":
            paths = resolve_job(root, args.book)
            extract_pdf(paths, force=args.force)
            print(f"Extracted raw text: jobs/{args.book}/text/raw.txt")
            print(f"next: pdftoaudio sanitize {args.book}")
            return 0

        parser.error(f"Command not wired yet: {args.command}")
        return 2

    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
