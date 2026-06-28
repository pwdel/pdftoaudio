from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .chunk import DEFAULT_MAX_BYTES, chunk_job
from .extract import extract_pdf
from .jobs import init_job, inspect_status, resolve_job
from .review import review_job
from .sanitize import sanitize_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdftoaudio",
        description="Turn PDFs into audiobooks through inspectable local job files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    command_parsers: dict[str, argparse.ArgumentParser] = {}

    init_parser = subparsers.add_parser("init", help="Create a job from a source PDF")
    command_parsers["init"] = init_parser
    init_parser.add_argument("book")
    init_parser.add_argument("pdf")
    init_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show job files and next step")
    command_parsers["status"] = status_parser
    status_parser.add_argument("book")

    extract_parser = subparsers.add_parser("extract", help="Extract PDF text")
    command_parsers["extract"] = extract_parser
    extract_parser.add_argument("book")
    extract_parser.add_argument("--force", action="store_true")

    sanitize_parser = subparsers.add_parser(
        "sanitize",
        help="Normalize safe text characters and write sanitize reports",
    )
    command_parsers["sanitize"] = sanitize_parser
    sanitize_parser.add_argument("book")
    sanitize_parser.add_argument("--force", action="store_true")
    sanitize_parser.add_argument("--report-only", action="store_true")

    review_parser = subparsers.add_parser(
        "review",
        help="Flag suspicious text spans without changing text",
    )
    command_parsers["review"] = review_parser
    review_parser.add_argument("book")
    review_parser.add_argument("--force", action="store_true")

    chunk_parser = subparsers.add_parser("chunk", help="Split cleaned text into TTS-sized chunks")
    command_parsers["chunk"] = chunk_parser
    chunk_parser.add_argument("book")
    chunk_parser.add_argument("--force", action="store_true")
    chunk_parser.add_argument("--source", choices=("cleaned", "sanitized"), default="cleaned")
    chunk_parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)

    help_parser = subparsers.add_parser("help", help="Show CLI help or command help")
    command_parsers["help"] = help_parser
    help_parser.add_argument("topic", nargs="?")
    parser.set_defaults(command_parsers=command_parsers)

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
        if args.command == "help":
            if args.topic is None:
                parser.print_help()
                return 0

            command_parser = args.command_parsers.get(args.topic)
            if command_parser is None:
                print(f"Unknown help topic: {args.topic}", file=sys.stderr)
                return 2

            command_parser.print_help()
            return 0

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

        if args.command == "sanitize":
            paths = resolve_job(root, args.book)
            sanitize_job(paths, force=args.force, report_only=args.report_only)
            print(f"Wrote sanitize report: jobs/{args.book}/reports/sanitize.json")
            if args.report_only:
                print(f"next: pdftoaudio sanitize {args.book}")
            else:
                print(f"next: pdftoaudio review {args.book}")
            return 0

        if args.command == "review":
            paths = resolve_job(root, args.book)
            report = review_job(paths, force=args.force)
            print(f"Wrote review report: jobs/{args.book}/reports/review.json")
            print(f"issues: {len(report['issues'])}")
            print(f"next: pdftoaudio clean {args.book} --mode codex")
            return 0

        if args.command == "chunk":
            paths = resolve_job(root, args.book)
            report = chunk_job(
                paths,
                source=args.source,
                max_bytes=args.max_bytes,
                force=args.force,
            )
            print(f"Wrote chunks: jobs/{args.book}/chunks/")
            print(f"chunks: {len(report['chunks'])}")
            print(f"next: pdftoaudio synthesize {args.book} --provider google")
            return 0

        parser.error(f"Command not wired yet: {args.command}")
        return 2

    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
