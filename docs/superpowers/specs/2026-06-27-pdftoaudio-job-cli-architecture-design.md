# pdftoaudio Job CLI Architecture Design

Date: 2026-06-27
Status: design approved; awaiting written-spec review

## Goal

Move `pdftoaudio` from a loose script collection to a small, job-first CLI that can support deterministic cleanup, Codex-assisted cleanup, MLX cleanup experiments, resumable synthesis, and clear user help without turning the project into a web app, queue system, or large framework.

The design implements the build-note promise from `index.html`:

```text
PDF -> raw text -> sanitized text -> review report -> cleaned text -> chunks -> voice -> MP3
```

The core rule is simple: keep the source PDF and cleanup work local, write inspectable files between steps, and send only cleaned chunks to hosted TTS.

## Non-Goals

- No web UI.
- No database.
- No daemon or background job runner.
- No A2A requirement in the first architecture.
- No full-book MLX cleanup until small text-slice benchmarks prove it is worth using.
- No live Google TTS calls in default tests.

## Architecture Principles

1. **Filesystem as the job database.** Each book gets a directory with predictable files.
2. **One CLI front door.** Users run `pdftoaudio <command> <book>`.
3. **Small commands.** Each command reads known inputs and writes known outputs.
4. **Source stays immutable.** The original PDF is copied into the job and never changed.
5. **Deterministic before LLM.** Sanitizers and review detectors run before Codex or MLX.
6. **Reports point to text.** Cleanup reports and review reports identify line ranges and reasons.
7. **Backends are swappable.** Codex, MLX, Google TTS, AWS Polly, and future local TTS are adapters.
8. **Resume by file presence.** Existing outputs are reused unless `--force` is passed.
9. **Keep the project small.** Prefer plain Python modules and `argparse` over frameworks.

## Job Workspace

Each book lives under `jobs/<book>/`.

```text
jobs/my-book/
  source/
    original.pdf
  text/
    raw.txt
    sanitized.txt
    cleaned.txt
  reports/
    sanitize.json
    line-map.json
    review.json
    cleanup.md
  chunks/
    001.txt
    002.txt
  audio/
    001.mp3
    002.mp3
    final.mp3
  manifest.json
```

The manifest tracks job metadata and step state. It should not store every edit. Detailed edits belong in reports.

Manifest fields:

- `book`: job name.
- `created_at`: ISO timestamp.
- `updated_at`: ISO timestamp.
- `source_pdf`: relative path to `source/original.pdf`.
- `steps`: map of step names to status, output path, timestamp, and last error.
- `settings`: selected voice, TTS provider, chunk size, cleanup mode.

## CLI Shape

New work targets a single CLI:

```bash
pdftoaudio <command> <book>
```

Commands:

```bash
pdftoaudio init my-book ./books/my-book.pdf
pdftoaudio extract my-book
pdftoaudio sanitize my-book
pdftoaudio review my-book
pdftoaudio clean my-book --mode codex
pdftoaudio clean my-book --mode mlx
pdftoaudio chunk my-book
pdftoaudio synthesize my-book --provider google --voice en-US-Casual-K
pdftoaudio stitch my-book
pdftoaudio status my-book
```

The existing `./read` script can stay as a compatibility wrapper during migration. New behavior should live behind `pdftoaudio`.

Help uses `argparse`:

```bash
pdftoaudio --help
pdftoaudio clean --help
pdftoaudio status my-book
```

`status` is the daily-use command. It reports which files exist, which steps are complete, failures from `manifest.json`, and the next suggested command.

Example:

```text
my-book
  source/original.pdf      ok
  text/raw.txt             ok
  text/sanitized.txt       ok
  reports/review.json      missing

next: pdftoaudio review my-book
```

## Data Flow

Each step has one clear input set and output set.

```text
init
  input:  external PDF path
  output: source/original.pdf, manifest.json

extract
  input:  source/original.pdf
  output: text/raw.txt

sanitize
  input:  text/raw.txt
  output: text/sanitized.txt, reports/sanitize.json, reports/line-map.json

review
  input:  text/sanitized.txt
  output: reports/review.json

clean --mode codex|mlx
  input:  text/sanitized.txt, reports/review.json
  output: text/cleaned.txt, reports/cleanup.md

chunk
  input:  text/cleaned.txt
  output: chunks/001.txt, chunks/002.txt, ...

synthesize
  input:  chunks/*.txt
  output: audio/001.mp3, audio/002.mp3, ...

stitch
  input:  audio/*.mp3
  output: audio/final.mp3
```

The CLI should refuse to run a step when required inputs are missing. A future `run` command may chain steps, but each individual command remains available.

## Cleanup Layers

Cleanup is split into deterministic passes and LLM passes.

### `sanitize`

`sanitize` may change text automatically, but only for deterministic, auditable rules.

Initial rules:

- Remove or replace control characters.
- Normalize nonbreaking spaces.
- Remove soft hyphens.
- Normalize repeated blank lines.
- Escape or flag SSML-sensitive characters.
- Flag suspicious Unicode clusters.
- Leave standalone page numbers for `review` findings in the first release.

Outputs:

- `text/sanitized.txt`: candidate text for review and cleanup.
- `reports/sanitize.json`: list of changes by raw line and sanitized line.
- `reports/line-map.json`: mapping from raw line numbers to sanitized line numbers.

### `review`

`review` does not change text. It marks suspicious regions for a human, Codex mode, or MLX mode.

Initial detectors:

- Likely page numbers.
- Repeated headers and footers.
- Hyphenated line breaks.
- Orphan lines.
- Long sentences.
- Table-like blocks.
- OCR-looking garbage.
- Odd Unicode clusters.
- Irregular capitalization or spacing.

Output:

- `reports/review.json`: line ranges, issue codes, severity, short explanation, and source excerpt.

### `clean --mode codex`

Codex mode is the quality baseline. It reads `text/sanitized.txt` and `reports/review.json`, focuses on flagged spans, writes `text/cleaned.txt`, and writes `reports/cleanup.md`.

Rules:

- Preserve meaning and order.
- Do not summarize.
- Report deletions and risky edits.
- Prefer small, reviewable patches over whole-book rewrites.

### `clean --mode mlx`

MLX mode uses the same inputs and outputs as Codex mode. It should not get a special pipeline. This lets us compare Codex and MLX on speed, quality, dropped text, and review burden.

MLX mode starts with small fixtures before any full-book run:

- Clean prose.
- Header/footer damage.
- Hyphenated line breaks.
- Long technical sentences.
- Table-like junk.

Measured fields:

- Wall time.
- Input and output character counts.
- Dropped text warnings.
- Number of review issues resolved.
- Human review notes.

## A2A Boundary

A2A is not part of the first implementation. The first boundary is the filesystem report format.

If A2A becomes useful later, it can wrap a cleanup backend without changing the job layout:

```text
text/sanitized.txt + reports/review.json -> A2A cleanup backend -> text/cleaned.txt + reports/cleanup.md
```

## Error Handling

Each command should:

- Check required inputs before doing work.
- Refuse to overwrite outputs unless `--force` is passed.
- Write to a temp file, then rename after success.
- Record success or failure in `manifest.json`.
- Print the next useful command after success.
- Print the missing input or failed output path on failure.

Examples:

- `extract` fails if `source/original.pdf` is missing.
- `sanitize` fails if `text/raw.txt` is missing.
- `chunk` fails if `text/cleaned.txt` is missing.
- `synthesize` skips MP3s that already exist unless `--force` is passed.
- `stitch` fails if expected audio order is incomplete.

## Testing Strategy

Tests stay small and local.

Unit tests:

- Job path resolution.
- Manifest read/write.
- Sanitizer rules.
- Review detectors.
- Chunk sizing and sentence boundary behavior.
- Status output for complete, incomplete, and failed jobs.

CLI smoke tests:

- Initialize a job from a tiny fixture.
- Run extract against a tiny PDF fixture if practical.
- Run sanitize, review, chunk, and status against text fixtures.
- Use a fake synthesizer for `synthesize`; do not call Google TTS by default.

MLX evaluation:

- Run only on text slices at first.
- Record metrics to `reports/mlx-eval.json`.
- Compare against Codex cleanup output where available.
- Treat MLX as experimental until it proves it can avoid dropped text and keep review time reasonable.

## Migration Plan

1. Add `pdftoaudio` CLI with `init` and `status`.
2. Move PDF extraction behind `pdftoaudio extract`.
3. Add `sanitize` with conservative rules and reports.
4. Add `review` detectors.
5. Move chunking behind `pdftoaudio chunk`.
6. Move Google TTS behind `pdftoaudio synthesize`.
7. Move stitching behind `pdftoaudio stitch`.
8. Add Codex cleanup mode.
9. Add MLX benchmark/evaluation mode.
10. Keep `./read` as a wrapper until the new CLI covers the old workflow.

## Implementation Defaults

Use these defaults for the first implementation plan:

- `sanitize` writes `text/sanitized.txt` by default, but only applies conservative character and whitespace fixes. Page-number removal starts as a review finding, not an automatic edit.
- Add `--report-only` to `sanitize` so rules can be inspected without writing `text/sanitized.txt`.
- Gitignore `jobs/` by default because it can contain source PDFs, generated text, audio, and credentials-adjacent metadata.
- Expose a root-level `./pdftoaudio` executable first. A package console script can come after the CLI shape settles.
- Keep report schemas small and versioned. Each JSON report includes `schema_version`, `book`, `generated_at`, input and output paths, and either a `changes` array or an `issues` array.
- Keep `manifest.json` focused on workflow state. Reports own detailed cleanup evidence.
